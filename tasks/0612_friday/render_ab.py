#!/usr/bin/env python3
"""PART 2 — pptx render A/B (4 gold pptx): [current prompt, meta] vs
[current prompt, meta + rendered PNG]. Isolates the render effect (prompt held
constant = the committed/current grader_judge_v2.md). Reuses ab_grade helpers +
vv.py render path (soffice->PyMuPDF). NOT committed.

Run: .venv/bin/python tasks/0612_friday/render_ab.py
"""
import base64, json, subprocess, sys, time, io
from pathlib import Path
sys.path.insert(0, "/Users/hsjeon/git/gdpval-realworks/tasks/0612_friday")
import ab_grade as ab  # reuse prep_env/build_client/gather_meta/resolve_file/parse_env/aggregate

PNG = ab.ROOT / "tasks/0612_friday/png"
MAX_PAGES = 8
_GLYPH_FIX = {"\u2011": "-"}


def _downsample(png, max_w=1200):
    from PIL import Image
    img = Image.open(io.BytesIO(png))
    if img.width <= max_w:
        return png
    h = int(img.height * max_w / img.width)
    img = img.resize((max_w, h), Image.LANCZOS).convert("RGB")
    b = io.BytesIO(); img.save(b, format="PNG", optimize=True)
    return b.getvalue()


def normalize_office(src, outdir):
    import zipfile
    dst = outdir / f"_norm_{src.name}"; outdir.mkdir(parents=True, exist_ok=True)
    changed = False
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename.endswith(".xml"):
                try:
                    txt = data.decode("utf-8"); new = txt
                    for a, b in _GLYPH_FIX.items():
                        if a in new:
                            new = new.replace(a, b); changed = True
                    data = new.encode("utf-8")
                except UnicodeDecodeError:
                    pass
            zout.writestr(info, data)
    return dst if changed else src


def render_pptx(src, prefix):
    import fitz
    outdir = PNG / f"_conv_{prefix}"; outdir.mkdir(parents=True, exist_ok=True)
    s = normalize_office(Path(src), outdir)
    prof = (outdir / "_lo_profile").resolve()
    subprocess.run(["soffice", f"-env:UserInstallation=file://{prof}", "--headless",
                    "--convert-to", "pdf", "--outdir", str(outdir), str(s)],
                   capture_output=True, timeout=240)
    pdfs = sorted(outdir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not pdfs:
        return []
    doc = fitz.open(str(pdfs[0])); outs = []
    for i in range(min(doc.page_count, MAX_PAGES)):
        pix = doc.load_page(i).get_pixmap(dpi=150)
        p = PNG / f"{prefix}_p{i+1}.png"; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(_downsample(pix.tobytes("png"))); outs.append(str(p))
    doc.close()
    return outs


def make_text(filename, meta, has_image):
    obs = json.dumps(meta, ensure_ascii=False, indent=1)[:9000]
    blocks = [
        "## Routing hint\n- modality: " + ("visual" if has_image else "formatting"),
        "## Rubric item to grade",
        f"- max_score: {int(ab.MAXSCORE)}\n- required: null\n- criterion:\n  {ab.CRIT}",
        "## Selected candidate deliverable file", f"- path: `{filename}`",
        "## Pre-gathered read_deliverable observations",
        "Treat the JSON below as authoritative tool results; you cannot call tools. "
        "Evidence MUST quote something visible here or in the attached image.",
        "```json\n" + obs + "\n```",
    ]
    if has_image:
        blocks.append("## Rendered image(s) attached below\nPNG pages of the deliverable "
                      "are attached. Judge the VISUAL formatting & style you SEE (layout, "
                      "hierarchy, whitespace, legibility, glyph/tofu corruption, finish) with "
                      "the metadata above. Ground evidence in a visible feature.")
    else:
        blocks.append("## No image\nJudge from the observations above only.")
    blocks.append("Return ONLY the JSON envelope now (no prose, no code fence).")
    return "\n\n".join(blocks)


def judge_img(client, instr, text, image_paths):
    content = [{"type": "input_text", "text": text}]
    for ip in (image_paths or []):
        b64 = base64.b64encode(Path(ip).read_bytes()).decode("ascii")
        content.append({"type": "input_image", "image_url": f"data:image/png;base64,{b64}"})
    last = None
    for attempt in range(4):
        try:
            r = client.responses.create(model=ab.MODEL, instructions=instr,
                input=[{"role": "user", "content": content}],
                reasoning={"effort": "medium"}, max_output_tokens=2400)
            return ab.parse_env(getattr(r, "output_text", "") or "")
        except Exception as e:
            last = e
            if any(k in str(e).lower() for k in ("429", "rate", "timeout")):
                time.sleep(3 * (attempt + 1)); continue
            raise
    raise last


def main():
    ab.prep_env(); client = ab.build_client()
    promptA = ab.instructions_from(subprocess.run(
        ["git", "-C", str(ab.ROOT), "show", "HEAD:batch-runner/prompts/grader_judge_v2.md"],
        capture_output=True, text=True).stdout)
    gold = json.load(open(ab.GOLD))["items"]
    g54 = {t["task_id"]: t for t in json.load(open(ab.GRADE54))["tasks"]}
    pptx = [g for g in gold if g["kind"] == "pptx"]
    rows = []; calls = 0
    for g in pptx:
        tid = g["task_id"]; owner = float(g["owner_score"])
        item = ab.overall_item(g54.get(tid, {}))
        unit_files = []
        if item and item.get("target_scope") == "split_children" and item.get("child_grades"):
            for c in item["child_grades"]:
                sp = c.get("selected_paths") or []; unit_files.append(sp[0] if sp else None)
        else:
            sp = (item or {}).get("selected_paths") or []
            unit_files.append(sp[0] if sp else g.get("deliverable_path"))
        meta_units, img_units = [], []
        for i, uf in enumerate(unit_files):
            ap = ab.resolve_file(tid, uf)
            if not ap:
                meta_units.append(None); img_units.append(None); continue
            m = ab.gather_meta(str(ap))
            pngs = render_pptx(str(ap), f"{tid[:8]}_{i}")
            meta_units.append((ap.name, m)); img_units.append(pngs)

        def arm(with_img):
            nonlocal calls
            us = []
            for k, mu in enumerate(meta_units):
                if mu is None:
                    us.append({"verdict": "fail", "partial": 0.0}); continue
                name, meta = mu
                imgs = img_units[k] if with_img else None
                res = judge_img(client, promptA, make_text(name, meta, bool(imgs)), imgs); calls += 1
                us.append(res)
            return ab.aggregate(us)

        awMeta = arm(False); awRender = arm(True)
        npng = sum(len(x or []) for x in img_units)
        rows.append({"id": tid[:8], "owner": owner, "meta": round(awMeta, 2),
                     "render": round(awRender, 2), "d_meta": round(awMeta - owner, 2),
                     "d_render": round(awRender - owner, 2), "pngs": npng})
        print(f"  {tid[:8]} owner={owner:.1f} meta={awMeta:.2f}(d{awMeta-owner:+.2f}) "
              f"render={awRender:.2f}(d{awRender-owner:+.2f}) pngs={npng}", flush=True)

    import statistics as st
    mae_meta = round(st.mean(abs(r["d_meta"]) for r in rows), 3)
    mae_render = round(st.mean(abs(r["d_render"]) for r in rows), 3)
    out = {"n": len(rows), "calls": calls, "prompt": "current/A (constant)",
           "meta_MAE": mae_meta, "render_MAE": mae_render,
           "delta_MAE": round(mae_render - mae_meta, 3),
           "meta_bias": round(st.mean(r["d_meta"] for r in rows), 3),
           "render_bias": round(st.mean(r["d_render"] for r in rows), 3), "rows": rows}
    json.dump(out, open(ab.ROOT / "tasks/0612_friday/render_result.json", "w"), ensure_ascii=False, indent=2)
    print("\n=== PART2 SUMMARY (pptx 4, prompt constant=current) ===")
    print(f"meta   MAE={mae_meta} bias={out['meta_bias']}")
    print(f"render MAE={mae_render} bias={out['render_bias']}")
    print(f"ΔMAE (render-meta) = {out['delta_MAE']}  (2-arm 0607 ref: -0.062)")


if __name__ == "__main__":
    main()
