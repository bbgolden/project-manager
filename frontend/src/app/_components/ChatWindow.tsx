"use client";

import { useState, useRef } from "react";
import Form from "next/form";
import { sendMessage } from "@/app/actions";

export default function ChatWindow({
    thread,
}: {
    thread: string,
}) {
    const [messages, setMessages] = useState<string[]>([]);
    const chatBoxRef = useRef<HTMLDivElement | null>(null);
    const chatMessagesRef = useRef<HTMLDivElement | null>(null);
    const chatBarRef = useRef<HTMLDivElement | null>(null);

    const loadMessage = (data: FormData) => {
        const message = data.get("chatMessage")!.toString().trim()

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

    const getMarginTop = (): number => {
        const chatBoxHeight = chatBoxRef.current!.offsetHeight;
        const chatMessagesHeight = chatMessagesRef.current?.offsetHeight;
        const chatBarHeight = chatBarRef.current!.clientHeight;

        if(chatMessagesHeight && chatMessagesHeight > chatBoxHeight) {
            return 0;
        }

        return chatBoxHeight - (chatMessagesHeight ? chatMessagesHeight : 0) - chatBarHeight;
    };

    return (
        <div className="h-full max-h-full">
            <div 
                ref={chatBoxRef} 
                className={`font-sans flex flex-col relative items-center bg-gray-950 rounded-4xl pt-4 pr-4 pl-4 h-full max-h-full overflow-y-auto`}
            >
                {messages.length == 0 ? (
                    <p className="mt-auto mr-auto ml-auto mb-[50px] text-4xl font-bold">
                        How can I help?
                    </p>
                ) : (
                    <div ref={chatMessagesRef} className={`flex flex-col items-center w-full pb-16`}>
                        {messages.map((message, index) => (
                            <div className="bg-gray-900 rounded-lg m-2 p-2.5 justify-center w-3/4" key={index}>
                                <p className={`text-md ${index % 2 == 0 ? "text-gray-100 text-right" : "text-red-100 text-left"}`}>
                                    {message}
                                </p>
                            </div>
                        ))}
                    </div>
                )}
                <div 
                    ref={chatBarRef}
                    className={`transition-[margin-top] duration-800 ease-out ${messages.length == 0 ? "relative mb-auto" : "sticky bottom-0"} font-sans flex flex-col items-center bg-gray-950 h-1/16 w-3/4`}
                    style={{ marginTop: messages.length == 0 ? "0" : `${getMarginTop()}px` }}
                >
                    <Form 
                        action={loadMessage} 
                        onSubmit={(event) => {
                            if(!event.currentTarget.chatMessage.value.trim()) {
                                event.preventDefault();
                            }
                        }}
                        className="flex relative -top-1/2 bg-gray-50  text-gray-900 text-md rounded-4xl p-2.5 dark:bg-gray-700 dark:text-white h-[50px] w-full"
                    >
                        <input 
                            name="chatMessage" 
                            placeholder="Ask about a project or create a new one"
                            className="flex-grow placeholder-gray-400" 
                            autoComplete="off" 
                        />
                        <button type="submit" className="ml-2">Send</button>
                    </Form>
                </div>
            </div>
        </div>
    );
}