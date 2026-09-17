import type { Metadata } from "next";
import RecordedStudio from "../showcase/RecordedStudio";
import manifest from "../../public/showcase/manifest.json";

export const metadata: Metadata = {
  title: "Director Demo — Local clip workflow",
  description: "A recorded demonstration of a local-first clip creation and extension workflow.",
};

export default function StudioPage() {
  return <RecordedStudio manifest={manifest} />;
}
