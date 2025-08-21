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
    const [selectedOption, setSelectedOption] = useState(placeholder || "");

    const handleSelect = (option: string) => {
        setSelectedOption(option);
        setter(option);
        setIsOpen(false);
    };

    return (
        <div className="relative block text-left w-full">
            <button 
                type="button" 
                className="inline-flex justify-center transition-color duration-400 ease-out h-12 w-full rounded-md shadow-sm px-4 py-2 bg-gray-800 text-lg font-medium hover:bg-gray-700 cursor-pointer" 
                onClick={() => setIsOpen(!isOpen)} 
                onBlur={() => setIsOpen(false)}
            >
                {selectedOption}
            </button>
            {isOpen && (
                <div 
                    className="origin-top-right absolute right-0 mt-2 w-56 z-10 rounded-md shadow-lg bg-gray-800 ring-1 ring-black ring-opacity-5 focus:outline-none"
                >
                    {options.map((option, index) => (
                        <a 
                            key={index} 
                            className="block px-4 py-2 text-lg transition-color duration-400 ease-out hover:bg-gray-700 cursor-pointer" 
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