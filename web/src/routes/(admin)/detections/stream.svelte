<script lang="ts">
	import CardOverlay from "$lib/components/card-overlay.svelte";
	import { Badge } from "$lib/components/ui/badge";


    type Props = {
        id: number;
        label: string;
        source: string;
    }

    let { id, label, source }: Props = $props();
	
</script>

<CardOverlay>
    <div class="aspect-video bg-black">
        <img
            src={`/detections/stream/${id}`}
            alt={`${label} live feed`}
            class="h-full w-full object-contain"
            loading="eager"
            decoding="async"
        />
    </div>

    {#snippet overlay()}
        <div class="flex flex-wrap items-center gap-2 text-xs">
            <Badge variant="secondary" class="bg-black/50 text-white">{label}</Badge>
            <Badge variant="secondary" class="bg-black/50 text-white">{source}</Badge>
        </div>
    {/snippet}
</CardOverlay>