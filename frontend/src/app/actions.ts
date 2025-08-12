"use server";

import { revalidateTag } from "next/cache";
import instance from "@/lib/api";

export async function sendMessage(
    message: string, 
    thread: string, 
    isFirstMessage: boolean,
): Promise<string> {
    const response = await instance.post("/chat", {
        "content": message,
        "threadID": thread,
        "isFirstMessage": isFirstMessage,
    });

    revalidateTag("status");
    return response.data.content;
}