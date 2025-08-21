export default function EmptyTaskList({
    currentProject,
}: {
    currentProject: string,
}) {
    return (
        <div className="justify-center">
            {currentProject === "" ? (
                <p className="text-center text-lg mt-4">
                    Select a project to view its tasks.
                </p>
            ) : (
                <p className="text-center text-lg mt-4">
                    It looks like there aren't any tasks for this project.
                </p>
            )}
        </div>
    )
}