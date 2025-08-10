"use client";

import { use, useState } from "react";
import type { StatusData } from "@/types";

export default function StatusWindow({
    status,
}: {
    status: Promise<StatusData>
}) {
    const [currentDisplay, setCurrentDisplay] = useState("timeline");
    const statusData = use(status);

    return (
        <div className="font-sans flex flex-col bg-gray-950 rounded-4xl p-4 h-full items-start">
            <ol className={currentDisplay == "actions" ? "block" : "hidden"}>
                {statusData.actions.map((action, index) => (
                    <li key={index}>
                        {action.name}
                    </li>
                ))}
            </ol>
            <ol className={currentDisplay == "timeline" ? "block" : "hidden"}>
                {statusData.timeline.map((task, index) => (
                    <li key={index}>
                        {task.taskName}
                    </li>
                ))}
            </ol>
        </div>
    );
}