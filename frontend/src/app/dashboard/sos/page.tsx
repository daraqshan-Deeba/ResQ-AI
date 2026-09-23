import { redirect } from "next/navigation";

/** SOS uses a confirmation popup. No dedicated page. */
export default function SosPage() {
  redirect("/dashboard");
}
