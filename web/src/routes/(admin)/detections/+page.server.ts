import fs from 'node:fs/promises';
import path from 'node:path';

export async function load({ url }) {
	const detectionsPath = path.resolve('detections');
    try {
        await fs.access(detectionsPath);
    } catch {
        return { images: [] };
    }
    const types = await fs.readdir(detectionsPath);

    const type = url.searchParams.get('type') || types?.at(0);
    if (!type) {
		return { images: [] };
	}
	const stage = url.searchParams.get('stage');
	
    let relativePath = type;
	if (stage === 'approved') {
        relativePath = path.join(relativePath, 'approved');
	} else if (stage === 'rejected') {
        relativePath = path.join(relativePath, 'rejected');
	}
    const absPath = path.join(detectionsPath, relativePath);

    try {
        await fs.access(absPath);
    } catch {
        return { images: [] };
    }

    const detections = (await fs.readdir(absPath)).filter((dir) => !['approved', 'rejected'].includes(dir));
    return { images: detections.map((detection) => path.join(relativePath, detection, 'best.jpg')) };
}