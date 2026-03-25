import { command, form, query } from "$app/server";
import { getConfig, saveConfig } from "./config.remote";
import * as v from "valibot";

export const getDetectors = query(async () => {
    const { config, app } = await getConfig();
    const lengthDiff = config.detectors.length - app.detectors.length;
    for (let i = 0; i < lengthDiff; i++) {
        app.detectors.push({ label: "Detector " + (app.detectors.length + 1) });
    }
    await saveConfig({ config, app });

    const detectorZip = config.detectors.map((detector, index) => {
        return { detector, meta: app.detectors[index] };
    });
    return detectorZip;
})

export const getDetector = query(
    v.object({
        label: v.string(),
    }),
    async ({ label }) => {
        const detectors = await getDetectors();
        return detectors.find((detector) => detector.meta.label === label);
    }
)

export const saveDetector = form(
    v.object({
        original: v.optional(v.string()),
        label: v.string(),
        detector: v.any()
    }),
    async ({ original, label, detector }) => {
        const { config, app } = await getConfig();
        if (original) {
            const index = app.detectors.findIndex((detector) => detector.label === original);
            config.detectors[index] = detector;
            app.detectors[index].label = label;
        } else {
            const lengthDiff = config.detectors.length - app.detectors.length;
            for (let i = 0; i < lengthDiff; i++) {
                app.detectors.push({ label: "Detector " + (app.detectors.length + 1) });
            }
            config.detectors.push(detector);
            app.detectors.push({ label });
        }
        await saveConfig({ config, app });
    })

export const deleteDetector = command(
    v.object({
        label: v.string(),
    }),
    async ({ label }) => {
        const { config, app } = await getConfig();
        const index = app.detectors.findIndex((detector) => detector.label === label);
        config.detectors.splice(index, 1);
        app.detectors.splice(index, 1);
        await saveConfig({ config, app });
    })


