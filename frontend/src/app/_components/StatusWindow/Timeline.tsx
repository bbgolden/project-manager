"use client";

import { useState } from "react";
import type { StatusData } from "@/types";
import SelectorDropdown from "@/app/_components/SelectorDropdown";
import InfoDropdown from "@/app/_components/InfoDropdown";

export default function TaskList({
    tasks,
}: {
    tasks: StatusData["timeline"],
}) {
    const [currentOrder, setCurrentOrder] = useState("End Date");

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
        <div>
            <div className="flex w-full justify-self-center items-center gap-[16px] mt-5">
                <p className="font-bold text-2xl">
                    Tasks Sorted By
                </p>
                <SelectorDropdown options={["Start Date", "End Date"]} placeholder="End Date" setter={setCurrentOrder} />
            </div>
            <ol>
                {tasks.toSorted(
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
    )
}