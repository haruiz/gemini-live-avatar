import { defineConfig } from 'vite';
import tailwindcss from "@tailwindcss/vite";
import importMap from './vite/importMap.js';
// import { resolve } from 'path';
//
// console.log(resolve(__dirname, './../../TalkingHead/modules/talkinghead.mjs'));

export default defineConfig(({ mode }) => ({
    build: {
        outDir: '../src/gemini_live_avatar/site',
        emptyOutDir: true
    },
    plugins: [
        tailwindcss(),
        importMap(mode, {
            three: "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js/+esm",
            "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/",
            talkinghead: "https://cdn.jsdelivr.net/gh/met4citizen/TalkingHead@1.5/modules/talkinghead.mjs"
        })
    ]
}));
