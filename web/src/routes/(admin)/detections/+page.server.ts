import fs from 'node:fs/promises';
import path from 'node:path';

export async function load({ url }) {
	const detectionsPath = path.resolve('detections');
    const types = await fs.readdir(detectionsPath);

    const type = url.searchParams.get('type') || types?.at(0);
    if (!type) {
		return { images: [] };
	}
	const stage = url.searchParams.get('stage');
	
    let targetPath = path.join(detectionsPath, type);
    let relativePath = type;
	if (stage === 'approved') {
		targetPath = path.join(targetPath, 'approved');
        relativePath = path.join(relativePath, 'approved');
	} else if (stage === 'rejected') {
		targetPath = path.join(targetPath, 'rejected');
        relativePath = path.join(relativePath, 'rejected');
	}

	try {
        try {
            await fs.access(targetPath);
        } catch {
            return { images: [] };
        }

		const detections = await fs.readdir(targetPath);
        const bestPromises = detections.map(async (detection) => {
            const detectionPath = path.join(targetPath, detection);
            const images = await fs.readdir(detectionPath);
            const scores = images.map((image) => {
                const parts = image.split('_');
                const score = Number(parts[1].replace('.jpg', ''));
                const file = path.join(relativePath, detection, image);
                return { file, score };
            });
            return scores.sort((a, b) => b.score - a.score).at(0)?.file;
        });
        const best = (await Promise.all(bestPromises)).filter((file): file is string => !!file);
		return { images: best };
	} catch (e) {
		console.error(e);
		return { images: [] };
	}
}