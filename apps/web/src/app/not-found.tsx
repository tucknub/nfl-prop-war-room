import { PlaceholderPage } from "@/components/placeholder-page";

export default function NotFound() {
  return (
    <PlaceholderPage
      eyebrow="Not found"
      title="This evidence view does not exist"
      description="The requested DepthSnap route is unavailable or has not been published."
    />
  );
}
