class Block:
    """Minecraft PI block description. Can be sent to Minecraft.setBlock/s"""
    def __init__(self, id, data=0):
        self.id = id
        self.data = data

    def __cmp__(self, rhs):
        return hash(self) - hash(rhs)

    def __eq__(self, rhs):
        return self.id == rhs.id and self.data == rhs.data

    def __hash__(self):
        return (self.id << 8) + self.data

    def withData(self, data):
        return Block(self.id, data)

    def __iter__(self):
        """Allows a Block to be sent whenever id [and data] is needed"""
        return iter((self.id, self.data))
        
    def __repr__(self):
        return "Block(%d, %d)"%(self.id, self.data)

AIR                 = Block(0)
STONE               = Block(1)
GRASS               = Block(2)
DIRT                = Block(3)
COBBLESTONE         = Block(4)
WOOD_PLANKS         = Block(5)
SAPLING             = Block(6)
BEDROCK             = Block(7)
WATER_FLOWING       = Block(8)
WATER               = WATER_FLOWING
WATER_STATIONARY    = Block(9)
LAVA_FLOWING        = Block(10)
LAVA                = LAVA_FLOWING
LAVA_STATIONARY     = Block(11)
SAND                = Block(12)
GRAVEL              = Block(13)
GOLD_ORE            = Block(14)
IRON_ORE            = Block(15)
COAL_ORE            = Block(16)
WOOD                = Block(17)
LEAVES              = Block(18)
GLASS               = Block(20)
LAPIS_LAZULI_ORE    = Block(21)
LAPIS_LAZULI_BLOCK  = Block(22)
SANDSTONE           = Block(24)
BED                 = Block(26)
COBWEB              = Block(30)
GRASS_TALL          = Block(31)
WOOL                = Block(35)
FLOWER_YELLOW       = Block(37)
FLOWER_CYAN         = Block(38)
MUSHROOM_BROWN      = Block(39)
MUSHROOM_RED        = Block(40)
GOLD_BLOCK          = Block(41)
IRON_BLOCK          = Block(42)
STONE_SLAB_DOUBLE   = Block(43)
STONE_SLAB          = Block(44)
BRICK_BLOCK         = Block(45)
TNT                 = Block(46)
BOOKSHELF           = Block(47)
MOSS_STONE          = Block(48)
OBSIDIAN            = Block(49)
TORCH               = Block(50)
FIRE                = Block(51)
STAIRS_WOOD         = Block(53)
CHEST               = Block(54)
DIAMOND_ORE         = Block(56)
DIAMOND_BLOCK       = Block(57)
CRAFTING_TABLE      = Block(58)
FARMLAND            = Block(60)
FURNACE_INACTIVE    = Block(61)
FURNACE_ACTIVE      = Block(62)
DOOR_WOOD           = Block(64)
LADDER              = Block(65)
STAIRS_COBBLESTONE  = Block(67)
DOOR_IRON           = Block(71)
REDSTONE_ORE        = Block(73)
SNOW                = Block(78)
ICE                 = Block(79)
SNOW_BLOCK          = Block(80)
CACTUS              = Block(81)
CLAY                = Block(82)
SUGAR_CANE          = Block(83)
FENCE               = Block(85)
GLOWSTONE_BLOCK     = Block(89)
BEDROCK_INVISIBLE   = Block(95)
STONE_BRICK         = Block(98)
IRON_BARS           = Block(101)
GLASS_PANE          = Block(102)
MELON               = Block(103)
FENCE_GATE          = Block(107)
GLOWING_OBSIDIAN    = Block(246)
NETHER_REACTOR_CORE = Block(247)
SANDSTONE_SLAB         = Block(44, 1)
SANDSTONE_SLAB_DOUBLE  = Block(43, 1)
COAL_BLOCK             = Block(173)
QUARTZ_BLOCK           = Block(155)
QUARTZ_PILLAR          = Block(155, 2)
QUARTZ_STAIRS          = Block(156)
HAY_BLOCK              = Block(170)
HAY_BLOCK_SIDE          = Block(170, 1)
HAY_BLOCK_TOP           = Block(170, 2)
PRISMARINE             = Block(168)
PRISMARINE_BRICKS       = Block(168, 1)
DARK_PRISMARINE         = Block(168, 2)
SEA_LANTERN             = Block(169)
SLIME_BLOCK             = Block(165)
HOPPER                  = Block(154)
BEACON                  = Block(138)
END_STONE               = Block(121)
END_ROD                 = Block(198)
PURPUR_BLOCK             = Block(201)
PURPUR_PILLAR            = Block(202)
PURPUR_STAIRS            = Block(203)
SHULKER_BOX             = Block(219)
CONCRETE_WHITE           = Block(251, 0)
CONCRETE_ORANGE          = Block(251, 1)
CONCRETE_MAGENTA         = Block(251, 2)
CONCRETE_LIGHT_BLUE      = Block(251, 3)
CONCRETE_YELLOW          = Block(251, 4)
CONCRETE_LIME            = Block(251, 5)
CONCRETE_PINK            = Block(251, 6)
CONCRETE_GRAY            = Block(251, 7)
CONCRETE_LIGHT_GRAY      = Block(251, 8)
CONCRETE_CYAN            = Block(251, 9)
CONCRETE_PURPLE          = Block(251, 10)
CONCRETE_BLUE            = Block(251, 11)
CONCRETE_BROWN           = Block(251, 12)
CONCRETE_GREEN           = Block(251, 13)
CONCRETE_RED             = Block(251, 14)
CONCRETE_BLACK           = Block(251, 15)

BLOCK_MAP = {
    "minecraft:air": AIR,
    "minecraft:stone": STONE,
    "minecraft:grass_block": GRASS,
    "minecraft:dirt": DIRT,
    "minecraft:cobblestone": COBBLESTONE,
    "minecraft:oak_planks": WOOD_PLANKS,
    "minecraft:sapling": SAPLING,
    "minecraft:bedrock": BEDROCK,
    "minecraft:water": WATER_FLOWING,
    "minecraft:water_flowing": WATER_FLOWING,
    "minecraft:water_stationary": WATER_STATIONARY,
    "minecraft:lava": LAVA_FLOWING,
    "minecraft:lava_flowing": LAVA_FLOWING,
    "minecraft:lava_stationary": LAVA_STATIONARY,
    "minecraft:sand": SAND,
    "minecraft:gravel": GRAVEL,
    "minecraft:gold_ore": GOLD_ORE,
    "minecraft:iron_ore": IRON_ORE,
    "minecraft:coal_ore": COAL_ORE,
    "minecraft:oak_log": WOOD,
    "minecraft:leaves": LEAVES,
    "minecraft:glass": GLASS,
    "minecraft:lapis_ore": LAPIS_LAZULI_ORE,
    "minecraft:lapis_block": LAPIS_LAZULI_BLOCK,
    "minecraft:sandstone": SANDSTONE,
    "minecraft:bed": BED,
    "minecraft:cobweb": COBWEB,
    "minecraft:tall_grass": GRASS_TALL,
    "minecraft:white_wool": WOOL,
    "minecraft:yellow_flower": FLOWER_YELLOW,
    "minecraft:red_flower": FLOWER_CYAN,
    "minecraft:brown_mushroom": MUSHROOM_BROWN,
    "minecraft:red_mushroom": MUSHROOM_RED,
    "minecraft:gold_block": GOLD_BLOCK,
    "minecraft:iron_block": IRON_BLOCK,
    "minecraft:double_stone_slab": STONE_SLAB_DOUBLE,
    "minecraft:stone_slab": STONE_SLAB,
    "minecraft:bricks": BRICK_BLOCK,
    "minecraft:tnt": TNT,
    "minecraft:bookshelf": BOOKSHELF,
    "minecraft:mossy_cobblestone": MOSS_STONE,
    "minecraft:obsidian": OBSIDIAN,
    "minecraft:torch": TORCH,
    "minecraft:fire": FIRE,
    "minecraft:oak_stairs": STAIRS_WOOD,
    "minecraft:chest": CHEST,
    "minecraft:diamond_ore": DIAMOND_ORE,
    "minecraft:diamond_block": DIAMOND_BLOCK,
    "minecraft:crafting_table": CRAFTING_TABLE,
    "minecraft:farmland": FARMLAND,
    "minecraft:furnace": FURNACE_INACTIVE,
    "minecraft:furnace_lit": FURNACE_ACTIVE,
    "minecraft:wooden_door": DOOR_WOOD,
    "minecraft:ladder": LADDER,
    "minecraft:cobblestone_stairs": STAIRS_COBBLESTONE,
    "minecraft:iron_door": DOOR_IRON,
    "minecraft:redstone_ore": REDSTONE_ORE,
    "minecraft:snow_layer": SNOW,
    "minecraft:ice": ICE,
    "minecraft:snow_block": SNOW_BLOCK,
    "minecraft:cactus": CACTUS,
    "minecraft:clay": CLAY,
    "minecraft:sugar_cane": SUGAR_CANE,
    "minecraft:fence": FENCE,
    "minecraft:glowstone": GLOWSTONE_BLOCK,
    "minecraft:invisible_bedrock": BEDROCK_INVISIBLE,
    "minecraft:stone_bricks": STONE_BRICK,
    "minecraft:glass_pane": GLASS_PANE,
    "minecraft:melon": MELON,
    "minecraft:fence_gate": FENCE_GATE,
    "minecraft:glowing_obsidian": GLOWING_OBSIDIAN,
    "minecraft:nether_reactor_core": NETHER_REACTOR_CORE,
    "minecraft:coal_block": COAL_BLOCK,
    "minecraft:quartz_block": QUARTZ_BLOCK,
    "minecraft:quartz_pillar": QUARTZ_PILLAR,
    "minecraft:quartz_stairs": QUARTZ_STAIRS,
    "minecraft:hay_block": HAY_BLOCK,
    "minecraft:prismarine": PRISMARINE,
    "minecraft:prismarine_bricks": PRISMARINE_BRICKS,
    "minecraft:dark_prismarine": DARK_PRISMARINE,
    "minecraft:sea_lantern": SEA_LANTERN,
    "minecraft:slime_block": SLIME_BLOCK,
    "minecraft:hopper": HOPPER,
    "minecraft:beacon": BEACON,
    "minecraft:end_stone": END_STONE,
    "minecraft:end_rod": END_ROD,
    "minecraft:purpur_block": PURPUR_BLOCK,
    "minecraft:purpur_pillar": PURPUR_PILLAR,
    "minecraft:purpur_stairs": PURPUR_STAIRS,
    "minecraft:shulker_box": SHULKER_BOX,
    "minecraft:concrete": CONCRETE_WHITE,  # default blanco
    "minecraft:concrete_white": CONCRETE_WHITE,
    "minecraft:concrete_orange": CONCRETE_ORANGE,
    "minecraft:concrete_magenta": CONCRETE_MAGENTA,
    "minecraft:concrete_light_blue": CONCRETE_LIGHT_BLUE,
    "minecraft:concrete_yellow": CONCRETE_YELLOW,
    "minecraft:concrete_lime": CONCRETE_LIME,
    "minecraft:concrete_pink": CONCRETE_PINK,
    "minecraft:concrete_gray": CONCRETE_GRAY,
    "minecraft:concrete_light_gray": CONCRETE_LIGHT_GRAY,
    "minecraft:concrete_cyan": CONCRETE_CYAN,
    "minecraft:concrete_purple": CONCRETE_PURPLE,
    "minecraft:concrete_blue": CONCRETE_BLUE,
    "minecraft:concrete_brown": CONCRETE_BROWN,
    "minecraft:concrete_green": CONCRETE_GREEN,
    "minecraft:concrete_red": CONCRETE_RED,
    "minecraft:concrete_black": CONCRETE_BLACK,
    "minecraft:iron_bars": IRON_BARS,
}

