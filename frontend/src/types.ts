export type StatusData = {
    projects: string[],
    actions: {
        name: string, 
        params: Record<string, any>,
    }[],
    timeline: {
        projectName: string,
        taskName: string,
        taskDesc: string | null,
        start: string,
        end: string | null,
    }[],
};