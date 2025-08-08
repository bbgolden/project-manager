import ChatWindow from "@/app/_components/chat";

export default function Home() {
  return (
    <div className="font-sans grid grid-rows-[50px_1fr_50px] justify-items-center min-h-screen p-8 sm:p-20">
      <main className="grid grid-rows-1 grid-cols-4 gap-[32px] row-start-2 items-center sm:items-start">
        <div className="row-span-full col-start-1 col-span-3">
          <ChatWindow thread={crypto.randomUUID()} />
        </div>
        <ol className="col-start-4 font-mono list-inside list-decimal text-sm/6 text-center sm:text-left">
          <li className="mb-2 tracking-[-.01em]">
            Get started by editing{" "}
            <code className="bg-black/[.05] dark:bg-white/[.06] font-mono font-semibold px-1 py-0.5 rounded">
              src/app/page.tsx
            </code>
            .
          </li>
          <li className="tracking-[-.01em]">
            Save and see your changes instantly.
          </li>
        </ol>
      </main>
    </div>
  );
}
