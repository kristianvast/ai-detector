import fs from 'node:fs';
import path from 'node:path';

export async function GET({ params }) {
    const detections = path.resolve('detections');
    const imgPath = path.join(detections, params.path);
	return new Response(fs.readFileSync(imgPath), {
		headers: {
			'Content-Type': 'image/jpeg'
		}
	});
}