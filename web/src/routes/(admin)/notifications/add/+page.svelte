<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { deleteTelegram, saveTelegram, testTelegram } from '$lib/remote/exporter.remote';

	let originalName = $state(page.url.searchParams.get('name') ?? '');
	let name = $state(originalName);
	let token = $state(page.url.searchParams.get('token') ?? '');
	let chat = $state(page.url.searchParams.get('chat') ?? '');
</script>

<section class="space-y-6">
	<header class="space-y-1">
		<h1 class="text-2xl font-semibold tracking-tight">Add Telegram</h1>
		<p class="text-sm text-muted-foreground">Add a new Telegram notification channel.</p>
	</header>

	<div class="flex justify-between gap-6">
		<form {...saveTelegram} class="flex w-lg flex-col gap-2">
			<Input type="hidden" name="original" value={originalName} />
			<Label for="name">Name</Label>
			<Input id="name" name="name" bind:value={name} placeholder="e.g. Groupchat X" />
			<Label for="token">Token</Label>
			<div class="flex gap-2">
				<Input
					id="token"
					name="token"
					bind:value={token}
					placeholder="e.g. 1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
				/>
			</div>
			<Label for="chat">Chat ID</Label>
			<div class="flex gap-2">
				<Input id="chat" name="chat" bind:value={chat} placeholder="e.g. 1234567890" />
				<Button variant="outline" onclick={() => testTelegram({ token, chat })}
					>Test notification</Button
				>
			</div>
			<div class="flex gap-2">
				{#if originalName}
					<Button
						onclick={() =>
							deleteTelegram({ name: originalName }).then(() => goto(resolve('/notifications')))}
						variant="destructive"
						class="flex-1">Delete</Button
					>
				{/if}
				<Button type="submit" class="flex-1">Save</Button>
			</div>
		</form>
	</div>
</section>
