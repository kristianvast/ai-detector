import { command, form, query } from "$app/server";
import { redirect } from "@sveltejs/kit";
import { getConfig, saveConfig } from "./config.remote";
import * as v from "valibot";

export const getTelegramConfig = query(async () => {
    const { app } = await getConfig();
    return app.telegrams;
})

export const saveTelegram = form(
    v.object({
        original: v.optional(v.string()),
        name: v.string(),
        token: v.string(),
        chat: v.string(),
    }),
    async ({ name, token, chat, original }) => {
        const { config, app } = await getConfig();
        let found = false;
        app.telegrams.forEach((telegram) => {
            if (telegram.name === original) {
                telegram.name = name;
                telegram.token = token;
                telegram.chat = chat;
                found = true;
            }
        });
        if (!found) {
            app.telegrams.push({ name, token, chat });
        }
        await saveConfig({ config, app });
        redirect(302, '/notifications');
    }
)

export const deleteTelegram = command(
    v.object({
        name: v.string(),
    }),
    async ({ name }) => {
        const { config, app } = await getConfig();
        const telegram = app.telegrams.find((telegram) => telegram.name === name);
        app.telegrams = app.telegrams.filter((telegram) => telegram.name !== name);
        if (telegram) {
            config.detectors.forEach((detector) => {
                if (detector.exporters?.telegram) {
                    if (Array.isArray(detector.exporters?.telegram)) {
                        detector.exporters.telegram = detector.exporters.telegram.filter((t) => t.token !== telegram.token || t.chat !== telegram.chat);
                    } else if (detector.exporters.telegram.token === telegram.token && detector.exporters.telegram.chat === telegram.chat) {
                        detector.exporters.telegram = undefined;
                    }
                }
            });
        }
        await saveConfig({ config, app });
    }
)

export const testTelegram = command(
    v.object({
        token: v.string(),
        chat: v.string(),
    }),
    async ({ token, chat }) => {
        const response = await fetch("https://api.telegram.org/bot" + token + "/sendMessage", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                chat_id: chat,
                text: "Test notification",
            }),
        });
        return response.json();
    }
)
