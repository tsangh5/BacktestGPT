# BacktestGPT Frontend

Next.js 15 (React 19, TypeScript) frontend for BacktestGPT. See the [root README](../README.md) for full project documentation.

## Development

```bash
npm install
npm run dev
```

The app expects the FastAPI backend at `http://localhost:8000` by default. Set `NEXT_PUBLIC_API_URL` to point elsewhere (a bare hostname is fine — `https://` is added automatically).

## Production

```bash
npm run build
npm start
```
