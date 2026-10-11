# Netlify Deployment for Phishing Simulator Frontend

This frontend is ready for static deployment on Netlify.

## Steps

1. Open Netlify and create a new site from Git.
2. Select the repository or drag-and-drop the `frontend/dist` folder.
3. Set the build command:
   ```bash
   npm run build
   ```
4. Set the publish directory:
   ```bash
   dist
   ```
5. Add the environment variable:
   ```bash
   VITE_API_BASE_URL=https://your-backend.example.com
   ```
6. Save and deploy.

## Important

- The frontend is configured to use `VITE_API_BASE_URL` at runtime.
- Do not deploy the `frontend/node_modules` folder.
- The backend must be hosted separately and exposed at the public URL you provide.

## Local build check

The frontend build has been verified locally using:

```bash
cd frontend
npm install
npm run build
```

The generated `dist/` folder is ready for deployment.
