import { command, form, query } from "$app/server";
import { getConfig, saveConfig } from "./config.remote";
import * as v from "valibot";

export const getDetectors = query(async () => {
    const { config } = await getConfig();
    return config.detectors;
})

export const saveDetector = form(
    v.object({
        index: v.optional(v.number()),
        label: v.string(),
        detector: v.any()
    }),
    async ({ index, label, detector }) => {
        const { config, app } = await getConfig();
        if (index !== undefined) {
            config.detectors[index] = detector;
            app.detectors[index].label = label;
        } else {
            config.detectors.push(detector);
            app.detectors.push({ label, index: config.detectors.length - 1 });
        }
        await saveConfig({ config, app });
    })

export const deleteDetector = command(
    v.object({
        index: v.number(),
    }),
    async ({ index }) => {
        const { config, app } = await getConfig();
        config.detectors.splice(index, 1);
        app.detectors.splice(index, 1);
        await saveConfig({ config, app });
    })


