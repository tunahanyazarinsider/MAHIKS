import axios, { AxiosError } from "axios";

const userApi = axios.create({
    baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
    headers: {
        "Content-Type": "application/json",
    },
});


export const login = async (email: string, password: string) => {
    try {
        const response = await userApi.post("/login", { email, password });
        return response.data;
    } catch (error) {
        const axiosError = error as AxiosError;
        console.log(axiosError.response?.data);
        throw error;
    }
}

export const register = async (name: string, email: string, password: string) => {
    try {
        const response = await userApi.post("/register", { name, email, password });
        return response.data;
    } catch (error) {
        const axiosError = error as AxiosError;
        console.log(axiosError.response?.data);
        throw error;
    }
}