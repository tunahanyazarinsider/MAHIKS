import axios, { AxiosError } from "axios";
import { QueryRequest } from "../models/QueryRequest";

const chatApi = axios.create({
    baseURL: import.meta.env.VITE_API_URL + "api" || "http://localhost:8000",
    headers: {
        "Content-Type": "application/json",
    },
});


export const chatRequest = async (queryRequest: QueryRequest) => {
    try {
        const response = await chatApi.post("/ask", queryRequest);
        console.log(response.data);
        return response.data;
    } catch (error) {
        const axiosError = error as AxiosError;
        console.log(axiosError.response?.data);
        throw error;
    }
}
