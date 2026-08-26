/// <reference types="astro/client" />

// Let `astro check` (TypeScript) see Vue single-file components as default
// exports; the Vue integration handles the actual compilation.
declare module '*.vue' {
	import type { DefineComponent } from 'vue';
	const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>;
	export default component;
}
