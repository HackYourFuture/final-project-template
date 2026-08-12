This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app). We made minor adjustments for Hack Your Future final project.

## Getting Started

Requires Node.js `>=24.19.0` (see `engines` in `package.json`).

First, install the dependencies and copy the example environment file:

```bash
npm install
cp .env.example .env.local
```

`BACKEND_API_URL` in `.env.local` should point at your running backend (see `../backend/README.md`), default `http://localhost:8080`.

Then run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `src/app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a font family created by Vercel. You can reuse it, replace it with another font, or add other styling tools such as Tailwind CSS.

## Lint

You can run the linter with `npm run lint` and format files with `npm run format`.

To automatically fix lint issues, run `npm run lint:fix`.
