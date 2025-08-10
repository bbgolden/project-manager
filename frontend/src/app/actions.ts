"use server";

import { revalidatePath } from "next/cache";
import instance from "@/lib/api";

export async function sendMessage(
    message: string, 
    thread: string, 
    isFirstMessage: boolean,
): Promise<string> {
    const response = await instance.post("/chat", {
        "content": message,
        "thread_id": thread,
        "is_first_message": isFirstMessage,
    });

    revalidatePath("/");
    return response.data.content;
}