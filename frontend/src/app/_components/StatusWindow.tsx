"use client";

import { use, useState } from "react";
import type { StatusData } from "@/types";
import SelectorDropdown from "@/app/_components/SelectorDropdown";
import InfoDropdown from "@/app/_components/InfoDropdown";

export default function StatusWindow({
    status,
}: {
    status: Promise<StatusData>
}) {
    const [currentDisplay, setCurrentDisplay] = useState("actions");
    const [currentProject, setCurrentProject] = useState("");
    const statusData = use(status);

    return (
        <div className="font-sans flex flex-col bg-gray-950 rounded-4xl gap-4 p-4 h-full items-start overflow-auto">
            <div className="flex w-full justify-center gap-[32px]">
                <button className="bg-blue-950 hover:bg-blue-900 p-2 rounded-xl" onClick={() => setCurrentDisplay("actions")}>
                    AI Actions
                </button>
                <button className="bg-blue-950 hover:bg-blue-900 p-2 rounded-xl" onClick={() => setCurrentDisplay("timeline")}>
                    Timeline
                </button>
            </div>
            <ol className={currentDisplay == "actions" ? "block" : "hidden"}>
                {statusData.actions.map(action => (
                    <li key={action.name}>
                        {action.name}
                    </li>
                ))}
            </ol>
            <div className={`w-full ${currentDisplay == "timeline" ? "block" : "hidden"}`}>
                <SelectorDropdown options={statusData.projects} setter={setCurrentProject} />
                <ol>
                    {statusData.timeline.filter(task => task.projectName == currentProject).map(task => (
                        <li key={task.taskName} className="mt-5">
                            <InfoDropdown 
                                titleLeft={task.taskName} 
                                titleRight={task.end ? task.start + " to " + task.end : task.start} 
                                content={task.taskDesc ? task.taskDesc : "No description is provided for this task"} 
                            />
                        </li>
                    ))}
                </ol>
            </div>
        </div>
    );
}