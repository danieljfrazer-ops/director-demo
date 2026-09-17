import RecordedStudio from "./showcase/RecordedStudio";
import manifest from "../public/showcase/manifest.json";

export default function Home() {
  return <RecordedStudio manifest={manifest} />;
}
