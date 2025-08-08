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
    const userMessageStyle = "text-gray-100 text-md text-shadow-blue-200 text-right";
    const agentMessageStyle = "text-red-100 text-md text-shadow-red-200 text-left";

    const loadMessage = (data: FormData) => {
        const message = data.get("message")!.toString()

        setMessages(prevMessages => [...prevMessages, message, "Thinking..."]);
        requestAnimationFrame(() => {
            setTimeout(() => {
                void submitMessage(message);
            }, 0);
        });
    };

    const submitMessage = async (message: string) => {
        const response = await sendMessage(message.toString(), thread, messages.length == 0);
        setMessages(prevMessages => {
            const messagesExcludeLast = prevMessages.filter(msg => msg != "Thinking...")
            return [...messagesExcludeLast, response]
        });
    };

    return (
        <div className="font-sans flex flex-col bg-gray-950 rounded-4xl p-4">
            {messages.map((message, index) => (
                <div className="bg-gray-900 rounded-lg m-2 p-2.5 justify-center" key={index}>
                    <p className={index % 2 == 0 ? userMessageStyle : agentMessageStyle}>
                            {message}
                    </p>
                </div>
            ))}

            <Form action={loadMessage} className="flex mt-auto bg-gray-50 border border-gray-300 text-gray-900 text-sm self-center rounded-lg focus:ring-blue-500 focus:border-blue-500 p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 w-11/12">
                <input name="message" className="flex-grow" />
                <button type="submit">Send</button>
            </Form>
        </div>
    );
}