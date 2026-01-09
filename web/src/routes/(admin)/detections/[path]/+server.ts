import fs from 'node:fs/promises';
import path from 'node:path';

export async function GET({ params }) {
    const detections = path.resolve('detections');
    const imgPath = path.join(detections, params.path);
	return new Response(await fs.readFile(imgPath), {
		headers: {
			'Content-Type': 'image/jpeg'
		}
	});
}