# sv

Everything you need to build a Svelte project, powered by [`sv`](https://github.com/sveltejs/cli).

## Creating a project

If you're seeing this, you've probably already done this step. Congrats!

```sh
# create a new project in the current directory
npx sv create

# create a new project in my-app
npx sv create my-app
```

## Developing

Once you've created a project and installed dependencies with `npm install` (or `pnpm install` or `yarn`), start a development server:

```sh
npm run dev

# or start the server and open the app in a new browser tab
npm run dev -- --open
```

## Building

To create a production version of your app:

```sh
npm run build
```

You can preview the production build with `npm run preview`.

> To deploy your app, you may need to install an [adapter](https://svelte.dev/docs/kit/adapters) for your target environment.

## FFmpeg runtime behavior

The `/live/:id` endpoint depends on FFmpeg.

- During CI builds, the workflow copies `ffmpeg-static` into `static/_internal/ffmpeg.exe` before building the Windows executable.
- At runtime, FFmpeg is resolved in this order:
  1. `FFMPEG_PATH` (absolute path or command name).
  2. Local `ffmpeg-static` binary, if available on disk.
  3. Sidecar candidates near the executable and current working directory.
  4. Embedded asset extraction from `/_internal/ffmpeg(.exe)` to a temp directory.
  5. `ffmpeg` in system `PATH`.
- Restart the app after changing `FFMPEG_PATH` or `PATH` because the resolved binary path is cached for the process lifetime.
