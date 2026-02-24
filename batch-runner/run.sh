#!/bin/bash
# 싱글 테스트 (전체 220개)
#python main.py --config experiments/exp002_single_baseline.yaml

# 테스트 모드 (10개 샘플로 빠르게 확인)
#python main.py --config experiments/exp002_single_baseline.yaml --test --execution-mode subprocess

#python main.py --config experiments/exp002_single_baseline.yaml --test --execution-mode code_interpreter
            
# All
#python main.py --config experiments/exp002_single_baseline.yaml --execution-mode subprocess

python main.py --config experiments/exp002_single_baseline.yaml --execution-mode code_interpreter