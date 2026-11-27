"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiGet } from "@/lib/api";
import { Loading } from "@/components/ui";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    apiGet("/auth/me")
      .then((me) => router.replace(me.organisations.length === 1 ? `/o/${me.organisations[0].id}/dashboard` : "/orgs"))
      .catch(() => router.replace("/login"));
  }, [router]);
  return <Loading />;
}
