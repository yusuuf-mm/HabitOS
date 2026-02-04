import { SVGProps } from "react";

export function HabitOSLogo(props: SVGProps<SVGSVGElement>) {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            {...props}
        >
            {/* Outer circle representing a target/goal */}
            <circle cx="12" cy="12" r="10" />

            {/* Inner optimization curve - like an upward trend */}
            <path d="M7 13 L10 10 L14 12 L17 8" strokeWidth="2.5" />

            {/* Small dot at peak to emphasize achievement */}
            <circle cx="17" cy="8" r="1.5" fill="currentColor" />

            {/* Subtle checkmark element integrated */}
            <path d="M8 12 L10 14 L13 11" strokeWidth="1.5" opacity="0.6" />
        </svg>
    );
}
