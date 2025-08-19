"use client";

import { useState } from "react";

export default function SelectorDropdown({
    options,
    placeholder,
    setter,
}: {
    options: string[],
    placeholder?: string,
    setter: (val: string) => void,
}) {
    const [isOpen, setIsOpen] = useState(false);
    const [selectedOption, setSelectedOption] = useState(placeholder ? placeholder : "");

    const handleSelect = (option: string) => {
        setSelectedOption(option);
        setter(option);
        setIsOpen(false);
    };

    return (
        <div className="relative block text-left w-full">
            <button 
                type="button" 
                className="inline-flex justify-center h-12 w-full rounded-md shadow-sm px-4 py-2 bg-gray-700 text-lg font-medium hover:bg-gray-500" 
                onClick={() => setIsOpen(!isOpen)} 
                onBlur={() => setIsOpen(false)}
            >
                {selectedOption}
            </button>
            {isOpen && (
                <div 
                    className="origin-top-right absolute right-0 mt-2 w-56 z-10 rounded-md shadow-lg bg-gray-700 ring-1 ring-black ring-opacity-5 focus:outline-none"
                >
                    {options.map((option, index) => (
                        <a 
                            key={index} 
                            className="block px-4 py-2 text-lg hover:bg-gray-500" 
                            onMouseDown={() => handleSelect(option)}
                        >
                            {option}
                        </a>
                    ))}
                </div>
            )}
        </div>
    );
}