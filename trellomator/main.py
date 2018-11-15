import bugzilla
import click
import contextlib
import json
import logging
import sys
import trello

LOG = logging.getLogger()
CFG = {}
BC = None
TC = None

logging.getLogger('urllib3').setLevel('ERROR')
logging.getLogger('bugzilla').setLevel('ERROR')


def process_card(card):
    if card.name.startswith(CFG['bugzilla']['url']):
        LOG.info('found card %s', card.name)


def process_checklist(checklist):
    for item in checklist.items:
        if item['name'].startswith(CFG['bugzilla']['url']):
            bugurl = item['name']
            bugid = bugurl.split('=')[1]
            bug = BC.getbug(bugid)
            new_name = CFG['checklist_item_format'].format(**vars(bug))
            LOG.info('renaming checklist item %s -> %s', item['name'], new_name)
            checklist.rename_checklist_item(item['name'], new_name)


def process_cards(cards, check_cards=False, check_checklists=False):
    for card in cards:
        if check_cards:
            LOG.debug('processing card %s (%s)', card.name, card.id)
            process_card(card)

        if check_checklists:
            for checklist in card.checklists:
                LOG.debug('processing checklist %s on card %s',
                          card.name, checklist.name)
                process_checklist(checklist)


@click.command()
@click.option('-f', '--config', type=click.File())
@click.option('-k', '--checklists', is_flag=True)
@click.option('-c', '--cards', is_flag=True)
@click.option('-s', '--search')
@click.option('-b', '--board', multiple=True)
@click.option('--debug', 'loglevel', flag_value='DEBUG')
@click.option('--verbose', 'loglevel', flag_value='INFO', default=True)
@click.option('--quiet', 'loglevel', flag_value='WARNING')
def main(config, checklists=False, cards=False,
         search=None, board=None, loglevel=None):
    global TC, BC

    logging.basicConfig(level=loglevel)

    if config is not None:
        with contextlib.closing(config) as fd:
            CFG.update(json.load(fd))

    LOG.debug('logging in to trello')
    TC = trello.TrelloClient(
        api_key=CFG['trello']['api_key'],
        api_secret=CFG['trello']['api_secret'],
    )

    LOG.debug('logging in to bugzilla @ %s', CFG['bugzilla']['url'])
    BC = bugzilla.Bugzilla(CFG['bugzilla']['url'])
    BC.login(CFG['bugzilla']['username'], CFG['bugzilla']['password'])

    board_ids = board if board else CFG.get('board_ids', [])

    if search:
        LOG.info('searching for %s', search)
        target_cards = TC.search(search,
                                 board_ids=board_ids,
                                 models='cards')
        process_cards(target_cards,
                      check_cards=cards,
                      check_checklists=checklists)
    else:
        for bid in board_ids:
            board = TC.get_board(bid)
            LOG.info('processing cards on board %s', board.name)
            target_cards = board.open_cards()
            process_cards(target_cards,
                          check_cards=cards,
                          check_checklists=checklists)


if __name__ == '__main__':
    main(sys.argv[1:], auto_envvar_prefix='TM')
