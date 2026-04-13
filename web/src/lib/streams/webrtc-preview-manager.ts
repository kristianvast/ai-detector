import { base } from '$app/paths';
import {
	WEBRTC_PREVIEW_ICE_GATHERING_TIMEOUT_MS,
	WEBRTC_PREVIEW_ICE_SERVERS,
	WEBRTC_PREVIEW_REBUILD_DEBOUNCE_MS,
	WEBRTC_PREVIEW_RECONNECT_DELAY_MS,
	WEBRTC_PREVIEW_SESSION_PATH
} from '$lib/streams/webrtc-preview-config';
import type { PreviewPhase, PreviewSnapshot } from '$lib/streams/webrtc-preview-types';

type Listener = (snapshot: PreviewSnapshot) => void;
type SessionResponse = {
	sessionId: string;
	answer: RTCSessionDescriptionInit;
};
type PagePhase = Exclude<PreviewPhase, 'live'>;
type CloseSessionOptions = {
	keepalive?: boolean;
	awaitDelete?: boolean;
};

const SESSION_ENDPOINT = `${base}${WEBRTC_PREVIEW_SESSION_PATH}`;
const INVALID_SOURCE_MESSAGE = 'Only RTSP and RTSPS sources are supported for preview.';
const DISCONNECTED_MESSAGE = 'WebRTC preview disconnected.';
const DEFAULT_ERROR_MESSAGE = 'Failed to start WebRTC preview.';
const ICE_TIMEOUT_MESSAGE = 'Timed out while gathering ICE candidates.';

function isRtspSource(source: string): boolean {
	return /^rtsps?:\/\//i.test(source.trim());
}

function createSnapshot(
	phase: PreviewPhase,
	mediaStream: MediaStream | null,
	error?: string
): PreviewSnapshot {
	return { phase, mediaStream, error };
}

async function waitForIceGatheringComplete(pc: RTCPeerConnection): Promise<void> {
	if (pc.iceGatheringState === 'complete') {
		return;
	}

	await new Promise<void>((resolve, reject) => {
		const timeoutId = window.setTimeout(() => {
			cleanup();
			reject(new Error('Timed out while gathering ICE candidates.'));
		}, WEBRTC_PREVIEW_ICE_GATHERING_TIMEOUT_MS);

		const onStateChange = () => {
			if (pc.iceGatheringState === 'complete') {
				cleanup();
				resolve();
			}
		};

		const cleanup = () => {
			window.clearTimeout(timeoutId);
			pc.removeEventListener('icegatheringstatechange', onStateChange);
		};

		pc.addEventListener('icegatheringstatechange', onStateChange);
	});
}

class PreviewManagerError extends Error {
	retriable: boolean;

	constructor(message: string, retriable = false) {
		super(message);
		this.retriable = retriable;
	}
}

function isRetriableError(error: unknown): boolean {
	if (error instanceof PreviewManagerError) {
		return error.retriable;
	}

	if (error instanceof TypeError) {
		return true;
	}

	return error instanceof Error && error.message === ICE_TIMEOUT_MESSAGE;
}

class WebRtcPreviewManager {
	private readonly listeners = new Map<string, Set<Listener>>();
	private readonly streams = new Map<string, MediaStream | null>();
	private pc: RTCPeerConnection | null = null;
	private sessionId: string | null = null;
	private rebuildTimer: ReturnType<typeof setTimeout> | null = null;
	private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
	private generation = 0;
	private lifecycleBound = false;
	private phase: PagePhase = 'connecting';
	private errorMessage: string | undefined;

	subscribe(source: string, listener: Listener): () => void {
		const normalizedSource = source.trim();
		let sourceListeners = this.listeners.get(normalizedSource);
		const isNewSource = !sourceListeners;

		if (!sourceListeners) {
			sourceListeners = new Set();
			this.listeners.set(normalizedSource, sourceListeners);
		}

		sourceListeners.add(listener);
		this.bindLifecycle();

		if (!isRtspSource(normalizedSource)) {
			listener(createSnapshot('error', null, INVALID_SOURCE_MESSAGE));
		} else {
			if (!this.streams.has(normalizedSource)) {
				this.streams.set(normalizedSource, null);
			}

			if (isNewSource) {
				if (this.pc || this.sessionId) {
					this.setPageState('reconnecting');
				} else {
					this.resetPageState();
				}

				this.scheduleRebuild();
			}

			listener(this.getSnapshot(normalizedSource));
		}

		return () => {
			const nextListeners = this.listeners.get(normalizedSource);
			if (!nextListeners) {
				return;
			}

			nextListeners.delete(listener);
			if (nextListeners.size > 0) {
				return;
			}

			this.listeners.delete(normalizedSource);
			this.streams.delete(normalizedSource);

			if (!isRtspSource(normalizedSource)) {
				return;
			}

			if (this.getActiveSources().length === 0) {
				this.generation += 1;
				this.clearTimers();
				this.resetPageState();
				void this.closeActiveSession();
				return;
			}

			this.scheduleRebuild();
		};
	}

	private bindLifecycle(): void {
		if (this.lifecycleBound || typeof window === 'undefined') {
			return;
		}

		this.lifecycleBound = true;
		window.addEventListener('pagehide', () => {
			this.generation += 1;
			this.clearTimers();
			void this.closeActiveSession({ keepalive: true, awaitDelete: false });
		});
	}

	private getActiveSources(): string[] {
		return [...this.listeners.keys()].filter((source) => isRtspSource(source));
	}

	private getSnapshot(source: string): PreviewSnapshot {
		const mediaStream = this.streams.get(source) ?? null;
		if (mediaStream) {
			return createSnapshot('live', mediaStream);
		}

		return createSnapshot(this.phase, null, this.errorMessage);
	}

	private notifySource(source: string): void {
		const sourceListeners = this.listeners.get(source);
		if (!sourceListeners) {
			return;
		}

		const snapshot = this.getSnapshot(source);
		for (const listener of sourceListeners) {
			listener(snapshot);
		}
	}

	private notifyActiveSources(): void {
		for (const source of this.getActiveSources()) {
			this.notifySource(source);
		}
	}

	private setPageState(phase: PagePhase, error?: string): void {
		this.phase = phase;
		this.errorMessage = error;
		this.notifyActiveSources();
	}

	private resetPageState(): void {
		this.phase = 'connecting';
		this.errorMessage = undefined;
	}

	private clearStreams(sources = this.getActiveSources()): void {
		for (const source of sources) {
			this.streams.set(source, null);
		}
	}

	private clearTimers(): void {
		if (this.rebuildTimer) {
			clearTimeout(this.rebuildTimer);
			this.rebuildTimer = null;
		}

		if (this.reconnectTimer) {
			clearTimeout(this.reconnectTimer);
			this.reconnectTimer = null;
		}
	}

	private scheduleRebuild(delay = WEBRTC_PREVIEW_REBUILD_DEBOUNCE_MS): void {
		if (this.rebuildTimer) {
			clearTimeout(this.rebuildTimer);
		}

		this.rebuildTimer = setTimeout(() => {
			this.rebuildTimer = null;
			void this.rebuildPeer();
		}, delay);
	}

	private scheduleReconnect(message: string): void {
		if (this.getActiveSources().length === 0 || this.reconnectTimer) {
			return;
		}

		this.reconnectTimer = setTimeout(() => {
			this.reconnectTimer = null;
			this.setPageState('reconnecting', message);
			void this.rebuildPeer();
		}, WEBRTC_PREVIEW_RECONNECT_DELAY_MS);
	}

	private async deleteSession(sessionId: string, options: CloseSessionOptions = {}): Promise<void> {
		const request = fetch(`${SESSION_ENDPOINT}/${encodeURIComponent(sessionId)}`, {
			method: 'DELETE',
			keepalive: options.keepalive ?? false
		}).catch(() => undefined);

		if (options.awaitDelete === false) {
			return;
		}

		await request;
	}

	private async closeActiveSession(options: CloseSessionOptions = {}): Promise<void> {
		const pc = this.pc;
		const sessionId = this.sessionId;

		this.pc = null;
		this.sessionId = null;

		if (pc) {
			pc.ontrack = null;
			pc.onconnectionstatechange = null;
			try {
				pc.close();
			} catch {
				// Ignore browser peer cleanup errors.
			}
		}

		if (sessionId) {
			await this.deleteSession(sessionId, options);
		}
	}

	private async rebuildPeer(): Promise<void> {
		const sources = this.getActiveSources();
		const hadSession = Boolean(this.pc || this.sessionId);
		this.reconnectTimer && clearTimeout(this.reconnectTimer);
		this.reconnectTimer = null;

		const generation = ++this.generation;
		await this.closeActiveSession();

		if (sources.length === 0) {
			return;
		}

		this.clearStreams(sources);
		this.setPageState(hadSession ? 'reconnecting' : 'connecting');

		const pc = new RTCPeerConnection({ iceServers: [...WEBRTC_PREVIEW_ICE_SERVERS] });
		const transceivers = sources.map(() => pc.addTransceiver('video', { direction: 'recvonly' }));
		let transientSessionId: string | null = null;

		pc.ontrack = (event) => {
			if (generation !== this.generation) {
				return;
			}

			const sourceIndex = transceivers.indexOf(event.transceiver);
			if (sourceIndex === -1) {
				return;
			}

			this.streams.set(sources[sourceIndex], new MediaStream([event.track]));
			this.notifySource(sources[sourceIndex]);
		};

		pc.onconnectionstatechange = () => {
			if (generation !== this.generation || this.pc !== pc) {
				return;
			}

			if (pc.connectionState === 'connected' || pc.connectionState === 'connecting') {
				return;
			}

			if (
				pc.connectionState === 'disconnected' ||
				pc.connectionState === 'failed' ||
				pc.connectionState === 'closed'
			) {
				this.clearStreams();
				this.setPageState('reconnecting', DISCONNECTED_MESSAGE);
				this.scheduleReconnect(DISCONNECTED_MESSAGE);
			}
		};

		try {
			await pc.setLocalDescription(await pc.createOffer());
			await waitForIceGatheringComplete(pc);

			const response = await fetch(SESSION_ENDPOINT, {
				method: 'POST',
				headers: {
					'content-type': 'application/json'
				},
				body: JSON.stringify({
					offer: pc.localDescription,
					sources
				})
			});

			if (!response.ok) {
				throw new PreviewManagerError(
					(await response.text()) || DEFAULT_ERROR_MESSAGE,
					response.status === 408 || response.status === 429 || response.status >= 500
				);
			}

			const { sessionId, answer } = (await response.json()) as SessionResponse;
			transientSessionId = sessionId;

			if (generation !== this.generation) {
				pc.close();
				await this.deleteSession(sessionId);
				return;
			}

			await pc.setRemoteDescription(answer);

			if (generation !== this.generation) {
				pc.close();
				await this.deleteSession(sessionId);
				return;
			}

			this.pc = pc;
			this.sessionId = sessionId;
		} catch (error) {
			pc.close();
			if (transientSessionId) {
				await this.deleteSession(transientSessionId);
			}

			if (generation !== this.generation) {
				return;
			}

			const message = error instanceof Error ? error.message : DEFAULT_ERROR_MESSAGE;
			this.clearStreams(sources);
			this.setPageState('error', message);
			if (isRetriableError(error)) {
				this.scheduleReconnect(message);
			}
		}
	}
}

let previewManager: WebRtcPreviewManager | null = null;

function getPreviewManager(): WebRtcPreviewManager {
	previewManager ??= new WebRtcPreviewManager();
	return previewManager;
}

export function subscribeToStreamPreview(source: string, listener: Listener): () => void {
	return getPreviewManager().subscribe(source, listener);
}
