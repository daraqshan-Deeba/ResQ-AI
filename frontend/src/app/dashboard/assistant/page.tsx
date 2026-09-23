import { redirect } from "next/navigation";

/** Chat opens as a side panel. No dedicated page. */
export default function AssistantPage() {
  redirect("/dashboard");
}
