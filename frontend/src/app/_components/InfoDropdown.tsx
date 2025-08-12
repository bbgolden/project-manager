"use client";

import { useState, useRef } from "react";

export default function InfoDropdown({
    titleLeft,
    titleRight,
    content,
}: {
    titleLeft: string,
    titleRight?: string,
    content: string,
}) {
    const [isOpen, setIsOpen] = useState(false);
    const contentRef = useRef<HTMLDivElement | null>(null);

    return (
        <div className="border border-gray-800 rounded-md overflow-hidden">
            <button
                className={`w-full text-left px-4 py-2 ${isOpen ? "bg-gray-500" : "bg-gray-700"} hover:bg-gray-500 rounded-t-md focus:outline-none`}
                onClick={() => setIsOpen(!isOpen)}
            >
                <div className="flex w-full justify-between">
                    <p>
                        {titleLeft}
                    </p>
                    {titleRight && (
                        <p>
                            {titleRight}
                        </p>
                    )}
                </div>
            </button>
            <div
                ref={contentRef}
                className={`duration-500 ease-in-out ${isOpen ? "h-auto" : "h-0"}`}
                style={{ height: isOpen ? `${contentRef.current!.scrollHeight}px` : "0" }}
            >
                <div className="px-4 py-2 bg-gray-700 rounded-b-md">
                    {content}
                </div>
            </div>
        </div>
    )
}