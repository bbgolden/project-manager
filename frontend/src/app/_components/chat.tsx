"use client";

import { useState } from "react";
import Form from "next/form";
import { sendMessage } from "@/app/actions";

export default function ChatWindow({
    thread,
}: {
    thread: string,
}) {
    const [messages, setMessages] = useState([] as string[]);

    const loadMessage = (data: FormData) => {
        const message = data.get("message")!.toString()

        setMessages(prevMessages => [...prevMessages, message]);
        requestAnimationFrame(() => {
            setTimeout(() => {
                void submitMessage(message);
            }, 0);
        });
    };

    const submitMessage = async (message: string) => {
        const response = await sendMessage(message.toString(), thread, messages.length == 0);
        setMessages(prevMessages => [...prevMessages, response]);
    };

    return (
        <div className="font-sans grid grid-rows-[20px_1fr_20px] items-center justify-items-center min-h-screen p-8 pb-20 gap-16 sm:p-20">
            <ul>
                {messages.map((message, index) => (
                    <li className={index % 2 == 0 ? "stroke-violet-300" : "via-red-300"} key={index}>
                        {message}
                    </li>
                ))}
            </ul>

            <Form action={loadMessage}>
                <input name="message" className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500" />
                <button type="submit">Send Message</button>
            </Form>
        </div>
    );
}