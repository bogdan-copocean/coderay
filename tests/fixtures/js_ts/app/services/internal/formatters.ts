type User = { id: number; name: string; email: string };

export const formatUserLabel = (user: User): string => {
    return `${user.name} <${user.email}>`;
};

export const formatScore = (raw: number): number => {
    const { PI, round } = Math;
    return round(PI * raw * raw * 100) / 100;
};
