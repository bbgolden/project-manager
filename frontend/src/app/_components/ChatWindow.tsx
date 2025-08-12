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
        const message = data.get("message")!.toString().trim()

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
        <div className="h-full max-h-full">
            <div className="font-sans flex flex-col bg-gray-950 rounded-t-4xl p-4 h-11/12 max-h-11/12 overflow-auto">
                {messages.map((message, index) => (
                    <div className="bg-gray-900 rounded-lg m-2 p-2.5 justify-center" key={index}>
                        <p className={`text-md ${index % 2 == 0 ? "text-gray-100 text-right" : "text-red-100 text-left"}`}>
                            {message}
                        </p>
                    </div>
                ))}
            </div>
            <div className="font-sans flex flex-col justify-center items-center bg-gray-950 rounded-b-4xl p-4 h-1/12">
                <Form 
                    action={loadMessage} 
                    onSubmit={(e) => {
                        if(!e.currentTarget.message.value.trim()) {
                            e.preventDefault();
                        }
                    }}
                    className="flex bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 w-11/12"
                >
                    <input name="chat-message" className="flex-grow" autoComplete="off" />
                    <button type="submit" className="ml-2">Send</button>
                </Form>
            </div>
        </div>
    );
}