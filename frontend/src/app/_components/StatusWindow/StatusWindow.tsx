"use client";

import { use, useState } from "react";
import type { StatusData } from "@/types";
import SelectorDropdown from "@/app/_components/SelectorDropdown";
import Timeline from "@/app/_components/StatusWindow/Timeline";
import EmptyTimeline from "@/app/_components/StatusWindow/EmptyTimeline"

export default function StatusWindow({
    status,
}: {
    status: Promise<StatusData>
}) {
    const [currentDisplay, setCurrentDisplay] = useState("actions");
    const [currentProject, setCurrentProject] = useState("");
    const statusData = use(status);
    const timeline = statusData.timeline.filter(task => task.projectName == currentProject);

    return (
        <div className="font-sans flex flex-col bg-gray-950 rounded-4xl gap-4 p-4 h-full items-start overflow-auto">
            <div className="flex w-full justify-center gap-[32px]">
                <button 
                    className={`transition-colors duration-400 ease-out ${currentDisplay == "actions" ? "bg-blue-900" : "bg-blue-950"} hover:bg-blue-900 p-2 rounded-xl cursor-pointer`} 
                    onClick={() => setCurrentDisplay("actions")}
                >
                    AI Actions
                </button>
                <button 
                    className={`transition-colors duration-400 ease-out ${currentDisplay == "timeline" ? "bg-blue-900" : "bg-blue-950"} hover:bg-blue-900 p-2 rounded-xl cursor-pointer`} 
                    onClick={() => setCurrentDisplay("timeline")}
                >
                    Timeline
                </button>
            </div>
            <ol className={currentDisplay == "actions" ? "block" : "hidden"}>
                {statusData.actions.length == 0 ? (
                    <div className="grid gap-[20px] justify-center">
                        <p className="text-md text-center">
                            It looks like there haven't been any actions in this session. 
                        </p>
                        <p className="text-lg font-bold text-center">
                            Send a chat message to get started.
                        </p>
                    </div>
                ) : (
                    <div>
                        {statusData.actions.map(action => (
                            <li key={action.name}>
                                {action.name}
                            </li>
                        ))}
                    </div>
                )}
            </ol>
            <div className={`w-full ${currentDisplay == "timeline" ? "block " : "hidden "}`}>
                <div className="flex w-full justify-self-center items-center gap-[16px]">
                    <p className="text-md font-bold">
                        Project:
                    </p>
                    <SelectorDropdown options={statusData.projects} setter={setCurrentProject} />
                </div>
                {timeline.length == 0 ? (
                    <EmptyTimeline currentProject={currentProject} />
                ) : (
                    <Timeline tasks={timeline} />
                )}
            </div>
        </div>
    );
}