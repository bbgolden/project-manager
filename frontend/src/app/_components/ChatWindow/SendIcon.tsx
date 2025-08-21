export default function SendIcon({
    className,
    fill,
    stroke,
}: {
    className?: string,
    fill?: string,
    stroke?: string,
}) {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            className={className}
        >
            <circle 
                cx="12" 
                cy="12" 
                r="10"
                fill={fill || "white"}
                stroke="none"
            />
            <path
                d="M9 11 l3 -3 l3 3 M12 8 v7" 
                fill="none"
                stroke={stroke || "black"}
                strokeLinecap="round" 
                strokeLinejoin="round" 
            />
        </svg>
    )
}