import type { AxiosResponse } from "axios";

export default async function StatusWindow({
    status,
}: {
    status: Promise<AxiosResponse<any, any>>
}) {
    const statusData: {
        actions: {
            name: string, 
            params: Record<string, any>,
        }[]
    } = (await status).data;

    return (
        <div className="font-sans flex flex-col bg-gray-950 rounded-4xl p-4 h-full">
            <ol>
                {statusData.actions.map((action, index) => (
                    <li key={index}>
                        {action.name}
                    </li>
                ))}
            </ol>
        </div>
    );
}