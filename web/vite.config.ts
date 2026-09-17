import vinext from "vinext";
import { defineConfig } from "vite";

// The public portfolio is a static export. It deliberately has no Worker,
// Pages Function, database, object-storage, or model-service dependency.
export default defineConfig({
  plugins: [vinext()],
});
