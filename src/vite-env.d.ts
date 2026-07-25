/// <reference types="vite/client" />

declare const __APP_VERSION__: string

interface ImportMetaEnv {
	readonly VITE_BUILD_SHA?: string
	readonly VITE_BUILD_REPOSITORY?: string
}
