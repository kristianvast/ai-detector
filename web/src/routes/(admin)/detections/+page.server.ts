import fs from 'node:fs';
import path from 'node:path';

export function load({ url }) {
	const detectionsPath = path.resolve('detections');
    const types = fs.readdirSync(detectionsPath);

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
        if (!fs.existsSync(targetPath)) {
            return { images: [] };
        }
		const detections = fs.readdirSync(targetPath);
        const best = detections.map((detection) => {
            const images = fs.readdirSync(path.join(targetPath, detection))
            const scores = images.map((image) => {
                const score = Number(image.split('_')[1].replace('.jpg', ''));
                const file = path.join(relativePath, detection, image);
                return { file, score };
            });
            return scores.sort((a, b) => b.score - a.score).at(0)?.file;
        }).filter((file): file is string => !!file);
		return { images: best };
	} catch (e) {
		console.error(e);
		return { images: [] };
	}
}