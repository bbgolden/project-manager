import { Suspense } from "react";
import { cookies } from "next/headers";
import type { StatusData } from "@/types";
import instance from "@/lib/api";
import ChatWindow from "@/app/_components/chat";
import StatusWindow from "@/app/_components/status";

export default async function Home() {
  const thread = (await cookies()).get("thread_id")?.value!;
  const status: Promise<StatusData> = instance.get("/chat?thread=" + thread).then(res => res.data);

  return (
    <div className="font-sans grid grid-rows-[50px_1fr_50px] justify-items-center h-screen max-h-screen p-8 sm:p-20">
      <main className="grid grid-rows-1 grid-cols-4 gap-[32px] row-start-2 items-center sm:items-start h-full max-h-full w-11/12">
        <div className="row-span-full col-start-1 col-span-3 h-full max-h-full">
          <ChatWindow thread={thread} />
        </div>
        <Suspense fallback={<div>Loading...</div>}>
          <div className="row-span-full col-start-4 h-full">
            <StatusWindow status={status} />
          </div>
        </Suspense>
      </main>
    </div>
  );
}
