#!/usr/bin/env python3

import pydbus
import pulsectl
import gi
gi.require_version('Playerctl', '2.0')
from gi.repository import Playerctl, GLib

AD_VOLUME = 0.25
PLAYERCTL_PLAYERTARGET = 'spotify'
PA_SINK_TARGET = 'Spotify'
PY_CLIENT = 'adspot'

class MeState():
  def __init__(self):
    self._advertRunning = False

  @property
  def advertRunning(self) -> bool:
      return self._advertRunning

  @advertRunning.setter
  def advertRunning(self, advertRunning: bool) -> None:
    self._advertRunning = advertRunning

origVolumePerSink = {}
changedSinkVolume = set()
state = MeState()

#def on_playback_status(player, status):
#    pass

def on_metadata(player, metadata, state):
  if metadata['xesam:title'] == 'Advertisement':
    if not state.advertRunning:
      state.advertRunning = True
      print('advert detected changing volume:')
      with pulsectl.Pulse(PY_CLIENT) as pulse:
        for index in lowerAllVolumes(pulse, origVolumePerSink.keys()):
          changedSinkVolume.add(index)
    else:
      print('still an advert, not touching anything yet')
  else:
    print('title: ' + metadata['xesam:title'])
    if state.advertRunning:
      state.advertRunning = False
      print('normal track detected restoring volume:')
      with pulsectl.Pulse(PY_CLIENT) as pulse:
        for restoredVolumeIndexes in restoreVolumeByIndex(pulse, changedSinkVolume, origVolumePerSink):
          changedSinkVolume.remove(restoredVolumeIndexes)
    else:
      pass
      #print('still no advert, no change detected')

spotifyPlayer = None
manager = Playerctl.PlayerManager()
for playerName in manager.props.player_names:
  if playerName.name == PLAYERCTL_PLAYERTARGET:
    print(PLAYERCTL_PLAYERTARGET)
    spotifyPlayer = Playerctl.Player.new_from_name(playerName)
    spotifyPlayer.connect('metadata', on_metadata, state)
    #spotifyPlayer.connect('playback-status::', on_playback_status, manager)
    manager.manage_player(spotifyPlayer)
  else:
    print('seen' + playerName.name)

def on_player_vanished(manager, player):
  print('some player gone')
  print(player)

#manager.connect('name-appeared',)
manager.connect('player-vanished', on_player_vanished)

def pulseGetMatchingSinkInputs(pulse):
  for sinkInput in pulse.sink_input_list():
    if sinkInput.name == PA_SINK_TARGET or sinkInput.proplist['media.name'] == PA_SINK_TARGET:
      yield sinkInput

def getOrigVolume(pulse):
  for spotifySinkInput in pulseGetMatchingSinkInputs(pulse):
    volume = round(spotifySinkInput.volume.values[0], 4)
    yield [spotifySinkInput.index, volume]

def lowerAllVolumes(pulse, knownVolumeIds):
  for spotifySinkInput in pulseGetMatchingSinkInputs(pulse):
    sinkIndex = spotifySinkInput.index
    if sinkIndex in knownVolumeIds:
      print('setting volume of sink ' + str(sinkIndex) + ' to ' + str(AD_VOLUME))
      pulse.volume_set_all_chans(spotifySinkInput, AD_VOLUME)
      yield sinkIndex
    else:
      print('new source?')
      print(spotifySinkInput)

def restoreVolumeByIndex(pulse, changedSinkVolume, origVolumePerSink):
  for spotifySinkInput in pulseGetMatchingSinkInputs(pulse):
    sinkIndex = spotifySinkInput.index
    if sinkIndex in changedSinkVolume:
      originalVolume = origVolumePerSink.get(sinkIndex, None)
      if originalVolume:
        print('restoring')
        print(originalVolume)
        pulse.volume_set_all_chans(spotifySinkInput, originalVolume)
        yield sinkIndex
      else:
        print('could not find original volume of')
        print(sinkIndex)

with pulsectl.Pulse(PY_CLIENT) as pulse:
  for index, volumeInfo in getOrigVolume(pulse):
    origVolumePerSink[index] = volumeInfo
  print('learned volumes')
  print(origVolumePerSink)

main = GLib.MainLoop()
main.run()

exit()
