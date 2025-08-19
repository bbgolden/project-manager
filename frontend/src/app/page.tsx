import { Suspense } from "react";
import { cookies } from "next/headers";
import { unstable_cacheTag as cacheTag } from "next/cache";
import type { StatusData } from "@/types";
import instance from "@/lib/api";
import ChatWindow from "@/app/_components/ChatWindow";
import StatusWindow from "@/app/_components/StatusWindow";

const getStatus = async (thread: string): Promise<StatusData> => {
  "use cache";
  cacheTag("status");
  return instance.get("/chat?thread=" + thread).then(res => res.data);
}

export default async function Home() {
  const thread = (await cookies()).get("threadID")?.value!;
  const status = getStatus(thread);

  return (
    <div className="font-sans grid grid-rows-[50px_minmax(0,1fr)_50px] justify-items-center h-screen max-h-screen p-8 sm:p-20">
      <main className="grid grid-rows-1 grid-cols-4 gap-[32px] row-start-2 items-center sm:items-start h-full max-h-full w-11/12 overflow-hidden">
        <div className="row-span-full col-start-1 col-span-3 h-full max-h-full overflow-hidden">
          <ChatWindow thread={thread} />
        </div>
        <Suspense fallback={<div>Loading...</div>}>
          <div className="row-span-full col-start-4 h-full max-h-full overflow-hidden">
            <StatusWindow status={status} />
          </div>
        </Suspense>
      </main>
    </div>
  );
}
