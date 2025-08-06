"use server";

import instance from "@/lib/api";

export async function sendMessage(message: string, thread: string, isFirstMessage: boolean) {
    const response = await instance.post("/chat", {
        "content": message,
        "thread_id": thread,
        "is_first_message": isFirstMessage,
    });

    return response.data.content;
}