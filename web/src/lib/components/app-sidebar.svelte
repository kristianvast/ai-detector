<script lang="ts">
	import NavUser from "./nav-user.svelte";
	import * as Sidebar from "$lib/components/ui/sidebar/index.js";
	import CommandIcon from "@lucide/svelte/icons/command";
	import type { ComponentProps } from "svelte";
	import NavMain from "./nav-main.svelte";
	import type { NavMenu, NavItem } from "./types";

	let { 
		title,
		subtitle,
		user,
		menu,
		secondaryMenu,
		ref = $bindable(null), 
		...restProps 
	}: {
		title: string;
		subtitle: string;
		menu: NavMenu[];
		secondaryMenu?: NavMenu[];
		user: {
			name?: string;
			email?: string;
			avatar?: string;
			items: NavItem[];
			logout: () => void;
		};
	} & ComponentProps<typeof Sidebar.Root> = $props();
</script>

<Sidebar.Root bind:ref variant="inset" {...restProps}>
	<Sidebar.Header>
		<Sidebar.Menu>
			<Sidebar.MenuItem>
				<Sidebar.MenuButton size="lg">
					{#snippet child({ props })}
						<a href="##" {...props}>
							<div
								class="bg-sidebar-primary text-sidebar-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg"
							>
								<CommandIcon class="size-4" />
							</div>
							<div class="grid flex-1 text-start text-sm leading-tight">
								<span class="truncate font-medium">{title}</span>
								<span class="truncate text-xs">{subtitle}</span>
							</div>
						</a>
					{/snippet}
				</Sidebar.MenuButton>
			</Sidebar.MenuItem>
		</Sidebar.Menu>
	</Sidebar.Header>
	<Sidebar.Content>
		{#each menu as item}
			<NavMain title={item.title} items={item.items} />
		{/each}
		{#each secondaryMenu || [] as item}
			<NavMain title={item.title} items={item.items} size="sm" class="mt-auto"/>
		{/each}
	</Sidebar.Content>
	<Sidebar.Footer>
		<NavUser {user} items={user.items} logout={user.logout} />
	</Sidebar.Footer>
</Sidebar.Root>
