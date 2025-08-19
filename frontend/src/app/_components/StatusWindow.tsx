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
    const [currentOrder, setCurrentOrder] = useState("End Date");
    const statusData = use(status);

    const startDateSort = (
        a: StatusData["timeline"][number], 
        b: StatusData["timeline"][number],
    ): number => a.start.localeCompare(b.start);

    const endDateSort = (
        a: StatusData["timeline"][number], 
        b: StatusData["timeline"][number],
    ): number => {
        if(a.end && !b.end) {
            return -1;
        } else if(b.end && !a.end) {
            return 1;
        } else if(!a.end && !b.end) {
            return 0;
        }

        return a.end!.localeCompare(b.end!);
    };

    return (
        <div className="font-sans flex flex-col bg-gray-950 rounded-4xl gap-4 p-4 h-full items-start overflow-auto">
            <div className="flex w-full justify-center gap-[32px]">
                <button 
                    className={`transition-colors duration-500 ease-out ${currentDisplay == "actions" ? "bg-blue-900" : "bg-blue-950"} hover:bg-blue-900 p-2 rounded-xl`} 
                    onClick={() => setCurrentDisplay("actions")}
                >
                    AI Actions
                </button>
                <button 
                    className={`transition-colors duration-500 ease-out ${currentDisplay == "timeline" ? "bg-blue-900" : "bg-blue-950"} hover:bg-blue-900 p-2 rounded-xl`} 
                    onClick={() => setCurrentDisplay("timeline")}
                >
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
            <div className={`w-full transition-discrete duration-200 ease-in-out ${currentDisplay == "timeline" ? "block" : "hidden opacity-0"}`}>
                <div className="flex w-full justify-self-center items-center gap-[16px]">
                    <p className="text-md font-bold">
                        Project:
                    </p>
                    <SelectorDropdown options={statusData.projects} setter={setCurrentProject} />
                </div>
                <div className="flex w-full justify-self-center items-center gap-[16px] mt-5">
                    <p className="font-bold text-2xl">
                        Tasks Sorted By
                    </p>
                    <SelectorDropdown options={["Start Date", "End Date"]} placeholder="End Date" setter={setCurrentOrder} />
                </div>
                <ol>
                    {statusData.timeline.filter(
                        task => task.projectName == currentProject,
                    ).toSorted(
                        currentOrder == "End Date" ? endDateSort : startDateSort,
                    ).map(task => (
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