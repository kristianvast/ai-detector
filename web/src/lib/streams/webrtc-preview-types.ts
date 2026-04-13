export type PreviewPhase = 'connecting' | 'live' | 'reconnecting' | 'error';

export type PreviewSnapshot = {
	phase: PreviewPhase;
	mediaStream: MediaStream | null;
	error?: string;
};
