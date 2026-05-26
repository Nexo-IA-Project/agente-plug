import { redirect } from "next/navigation";
import { use } from "react";

export default function FollowupFlowDetailRedirect({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  redirect(`/onboarding/${id}`);
}
