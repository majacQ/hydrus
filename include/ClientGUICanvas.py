import HydrusConstants as HC
import ClientConstants as CC
import ClientData
import ClientCaches
import ClientFiles
import ClientGUICommon
import ClientGUIDialogs
import ClientGUIDialogsManage
import ClientGUIHoverFrames
import ClientMedia
import ClientRatings
import collections
import gc
import HydrusImageHandling
import HydrusTags
import HydrusVideoHandling
import os
import Queue
import random
import shutil
import time
import traceback
import urllib
import wx
import wx.media
import HydrusData
import HydrusFileHandling
import HydrusGlobals

if HC.PLATFORM_WINDOWS: import wx.lib.flashwin

ID_TIMER_VIDEO = wx.NewId()
ID_TIMER_RENDER_WAIT = wx.NewId()
ID_TIMER_ANIMATION_BAR_UPDATE = wx.NewId()
ID_TIMER_SLIDESHOW = wx.NewId()
ID_TIMER_CURSOR_HIDE = wx.NewId()
ID_TIMER_HOVER_SHOW = wx.NewId()

ANIMATED_SCANBAR_HEIGHT = 20
ANIMATED_SCANBAR_CARET_WIDTH = 10

# Zooms

ZOOMINS = [ 0.01, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.5, 2.0, 3.0, 5.0, 10.0, 20.0 ]
ZOOMOUTS = [ 20.0, 10.0, 5.0, 3.0, 2.0, 1.5, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.5, 0.3, 0.2, 0.15, 0.1, 0.05, 0.01 ]

NON_ZOOMABLE_MIMES = list( HC.AUDIO ) + [ HC.APPLICATION_PDF ]

EMBED_BUTTON_MIMES = [ HC.VIDEO_FLV, HC.APPLICATION_FLASH ]

def CalculateCanvasZoom( media, ( canvas_width, canvas_height ) ):
    
    ( media_width, media_height ) = media.GetResolution()
    
    if media_width == 0 or media_height == 0: return 1.0
    
    if ShouldHaveAnimationBar( media ): canvas_height -= ANIMATED_SCANBAR_HEIGHT
    
    if media.GetMime() in EMBED_BUTTON_MIMES:
        
        canvas_height -= 10
        canvas_width -= 10
        
    
    width_zoom = canvas_width / float( media_width )
    
    height_zoom = canvas_height / float( media_height )
    
    canvas_zoom = min( ( width_zoom, height_zoom ) )
    
    return canvas_zoom
    
def CalculateMediaContainerSize( media, zoom ):
    
    ( media_width, media_height ) = CalculateMediaSize( media, zoom )
    
    if ShouldHaveAnimationBar( media ): media_height += ANIMATED_SCANBAR_HEIGHT
    
    return ( media_width, media_height )
    
def CalculateMediaSize( media, zoom ):
    
    if media.GetMime() == HC.APPLICATION_PDF: ( original_width, original_height ) = ( 200, 45 )
    elif media.GetMime() in HC.AUDIO: ( original_width, original_height ) = ( 360, 240 )
    else: ( original_width, original_height ) = media.GetResolution()
    
    media_width = int( round( zoom * original_width ) )
    media_height = int( round( zoom * original_height ) )
    
    return ( media_width, media_height )
    
def ShouldHaveAnimationBar( media ):
    
    is_animated_gif = media.GetMime() == HC.IMAGE_GIF and media.HasDuration()
    
    is_animated_flash = media.GetMime() == HC.APPLICATION_FLASH and media.HasDuration()
    
    is_native_video = media.GetMime() in HC.NATIVE_VIDEO
    
    return is_animated_gif or is_animated_flash or is_native_video
    
class Animation( wx.Window ):
    
    def __init__( self, parent, media, initial_size, initial_position ):
        
        wx.Window.__init__( self, parent, size = initial_size, pos = initial_position )
        
        self.SetDoubleBuffered( True )
        
        self._media = media
        self._video_container = None
        
        self._animation_bar = None
        
        self._current_frame_index = 0
        self._current_frame_drawn = False
        self._current_frame_drawn_at = 0.0
        
        self._paused = False
        
        self._canvas_bmp = wx.EmptyBitmap( 0, 0, 24 )
        
        self._timer_video = wx.Timer( self, id = ID_TIMER_VIDEO )
        
        self._paused = False
        
        self.Bind( wx.EVT_PAINT, self.EventPaint )
        self.Bind( wx.EVT_SIZE, self.EventResize )
        self.Bind( wx.EVT_TIMER, self.TIMEREventVideo, id = ID_TIMER_VIDEO )
        self.Bind( wx.EVT_MOUSE_EVENTS, self.EventPropagateMouse )
        self.Bind( wx.EVT_KEY_UP, self.EventPropagateKey )
        self.Bind( wx.EVT_ERASE_BACKGROUND, self.EventEraseBackground )
        
        self.EventResize( None )
        
        self._timer_video.Start( 16, wx.TIMER_ONE_SHOT )
        
    
    def __del__( self ):
        
        wx.CallLater( 500, gc.collect )
        
    
    def _DrawFrame( self ):
        
        dc = wx.BufferedDC( wx.ClientDC( self ), self._canvas_bmp )
        
        current_frame = self._video_container.GetFrame( self._current_frame_index )
        
        ( my_width, my_height ) = self._canvas_bmp.GetSize()
        
        ( frame_width, frame_height ) = current_frame.GetSize()
        
        x_scale = my_width / float( frame_width )
        y_scale = my_height / float( frame_height )
        
        dc.SetUserScale( x_scale, y_scale )
        
        wx_bmp = current_frame.GetWxBitmap()
        
        dc.DrawBitmap( wx_bmp, 0, 0 )
        
        wx.CallAfter( wx_bmp.Destroy )
        
        dc.SetUserScale( 1.0, 1.0 )
        
        if self._animation_bar is not None: self._animation_bar.GotoFrame( self._current_frame_index )
        
        self._current_frame_drawn = True
        
        now_in_ms = HydrusData.GetNowPrecise()
        frame_was_supposed_to_be_at = self._current_frame_drawn_at + ( self._video_container.GetDuration( self._current_frame_index ) / 1000 )
        
        if 1000.0 * ( now_in_ms - frame_was_supposed_to_be_at ) > 16.7: self._current_frame_drawn_at = now_in_ms
        else: self._current_frame_drawn_at = frame_was_supposed_to_be_at
        
    
    def _DrawWhite( self ):
        
        dc = wx.BufferedDC( wx.ClientDC( self ), self._canvas_bmp )
        
        dc.SetBackground( wx.Brush( wx.Colour( *HC.options[ 'gui_colours' ][ 'media_background' ] ) ) )
        
        dc.Clear()
        
    
    def CurrentFrame( self ): return self._current_frame_index
    
    def EventEraseBackground( self, event ): pass
    
    def EventPaint( self, event ): wx.BufferedPaintDC( self, self._canvas_bmp )
    
    def EventPropagateKey( self, event ):
        
        event.ResumePropagation( 1 )
        event.Skip()
        
    
    def EventPropagateMouse( self, event ):
        
        screen_position = self.ClientToScreen( event.GetPosition() )
        ( x, y ) = self.GetParent().ScreenToClient( screen_position )
        
        event.SetX( x )
        event.SetY( y )
        
        event.ResumePropagation( 1 )
        event.Skip()
        
    
    def EventResize( self, event ):
        
        ( my_width, my_height ) = self.GetClientSize()
        
        ( current_bmp_width, current_bmp_height ) = self._canvas_bmp.GetSize()
        
        if my_width != current_bmp_width or my_height != current_bmp_height:
            
            if my_width > 0 and my_height > 0:
                
                if self._video_container is None: self._video_container = HydrusVideoHandling.VideoContainer( self._media, ( my_width, my_height ) )
                else:
                    
                    ( image_width, image_height ) = self._video_container.GetSize()
                    
                    we_just_zoomed_in = my_width > image_width
                    
                    if we_just_zoomed_in and self._video_container.IsScaled():
                        
                        full_resolution = self._video_container.GetResolution()
                        
                        self._video_container = HydrusVideoHandling.VideoContainer( self._media, full_resolution )
                        
                        self._video_container.SetFramePosition( self._current_frame_index )
                        
                        self._current_frame_drawn = False
                        
                    
                
                wx.CallAfter( self._canvas_bmp.Destroy )
                
                self._canvas_bmp = wx.EmptyBitmap( my_width, my_height, 24 )
                
                if self._video_container.HasFrame( self._current_frame_index ): self._DrawFrame()
                else: self._DrawWhite()
                
                self._timer_video.Start( 1, wx.TIMER_ONE_SHOT )
                
                
            
        
    
    def GotoFrame( self, frame_index ):
        
        if frame_index != self._current_frame_index:
            
            self._current_frame_index = frame_index
            
            self._video_container.SetFramePosition( self._current_frame_index )
            
            self._current_frame_drawn_at = 0.0
            self._current_frame_drawn = False
            
            if self._video_container.HasFrame( self._current_frame_index ): self._DrawFrame()
            else: self._DrawWhite()
            
            self._timer_video.Start( 1, wx.TIMER_ONE_SHOT )
            
        
        self._paused = True
        
    
    def Play( self ):
        
        self._paused = False
        
        self._timer_video.Start( 1, wx.TIMER_ONE_SHOT )
        
    
    def SetAnimationBar( self, animation_bar ): self._animation_bar = animation_bar
    
    def TIMEREventVideo( self, event ):
        
        MIN_TIMER_TIME = 4
        
        if self.IsShown():
            
            if self._current_frame_drawn:
                
                ms_since_current_frame_drawn = int( 1000.0 * ( HydrusData.GetNowPrecise() - self._current_frame_drawn_at ) )
                
                time_to_update = ms_since_current_frame_drawn + MIN_TIMER_TIME / 2 > self._video_container.GetDuration( self._current_frame_index )
                
                if not self._paused and time_to_update:
                    
                    num_frames = self._media.GetNumFrames()
                    
                    self._current_frame_index = ( self._current_frame_index + 1 ) % num_frames
                    
                    self._current_frame_drawn = False
                    
                    self._video_container.SetFramePosition( self._current_frame_index )
                    
                
            
            if not self._current_frame_drawn and self._video_container.HasFrame( self._current_frame_index ): self._DrawFrame()
            
            if not self._current_frame_drawn or not self._paused:
                
                ms_since_current_frame_drawn = int( 1000.0 * ( HydrusData.GetNowPrecise() - self._current_frame_drawn_at ) )
                
                ms_until_next_frame = max( MIN_TIMER_TIME, self._video_container.GetDuration( self._current_frame_index ) - ms_since_current_frame_drawn )
                
                self._timer_video.Start( ms_until_next_frame, wx.TIMER_ONE_SHOT )
                
            
        
    
class AnimationBar( wx.Window ):
    
    def __init__( self, parent, media, media_window ):
        
        ( parent_width, parent_height ) = parent.GetClientSize()
        
        wx.Window.__init__( self, parent, size = ( parent_width, ANIMATED_SCANBAR_HEIGHT ), pos = ( 0, parent_height - ANIMATED_SCANBAR_HEIGHT ) )
        
        self._dirty = True
        
        self._canvas_bmp = wx.EmptyBitmap( parent_width, ANIMATED_SCANBAR_HEIGHT, 24 )
        
        self.SetCursor( wx.StockCursor( wx.CURSOR_ARROW ) )
        
        self._media = media
        self._media_window = media_window
        self._num_frames = self._media.GetNumFrames()
        self._current_frame_index = 0
        
        self._currently_in_a_drag = False
        
        self.Bind( wx.EVT_MOUSE_EVENTS, self.EventMouse )
        self.Bind( wx.EVT_TIMER, self.TIMEREventUpdate, id = ID_TIMER_ANIMATION_BAR_UPDATE )
        self.Bind( wx.EVT_PAINT, self.EventPaint )
        self.Bind( wx.EVT_SIZE, self.EventResize )
        self.Bind( wx.EVT_ERASE_BACKGROUND, self.EventEraseBackground )
        
        self._timer_update = wx.Timer( self, id = ID_TIMER_ANIMATION_BAR_UPDATE )
        self._timer_update.Start( 100, wx.TIMER_CONTINUOUS )
        
    
    def _Redraw( self ):
        
        ( my_width, my_height ) = self._canvas_bmp.GetSize()
        
        dc = wx.MemoryDC( self._canvas_bmp )
        
        dc.SetPen( wx.TRANSPARENT_PEN )
        
        dc.SetBrush( wx.Brush( wx.SystemSettings.GetColour( wx.SYS_COLOUR_BTNFACE ) ) )
        
        dc.DrawRectangle( 0, 0, my_width, ANIMATED_SCANBAR_HEIGHT )
        
        #
        
        dc.SetBrush( wx.Brush( wx.SystemSettings.GetColour( wx.SYS_COLOUR_BTNSHADOW ) ) )
        
        dc.DrawRectangle( int( float( my_width - ANIMATED_SCANBAR_CARET_WIDTH ) * float( self._current_frame_index ) / float( self._num_frames - 1 ) ), 0, ANIMATED_SCANBAR_CARET_WIDTH, ANIMATED_SCANBAR_HEIGHT )
        
        #
        
        dc.SetFont( wx.SystemSettings.GetFont( wx.SYS_DEFAULT_GUI_FONT ) )
        
        dc.SetTextForeground( wx.BLACK )
        
        s = HydrusData.ConvertValueRangeToPrettyString( self._current_frame_index + 1, self._num_frames )
        
        ( x, y ) = dc.GetTextExtent( s )
        
        dc.DrawText( s, my_width - x - 3, 3 )
        
        self._dirty = False
        
    
    def EventEraseBackground( self, event ): pass
    
    def EventMouse( self, event ):
        
        CC.CAN_HIDE_MOUSE = False
        
        ( my_width, my_height ) = self.GetClientSize()
        
        if event.Dragging(): self._currently_in_a_drag = True
        
        if event.ButtonIsDown( wx.MOUSE_BTN_ANY ):
            
            ( x, y ) = event.GetPosition()
            
            compensated_x_position = x - ( ANIMATED_SCANBAR_CARET_WIDTH / 2 )
            
            proportion = float( compensated_x_position ) / float( my_width - ANIMATED_SCANBAR_CARET_WIDTH )
            
            if proportion < 0: proportion = 0
            if proportion > 1: proportion = 1
            
            self._current_frame_index = int( proportion * ( self._num_frames - 1 ) + 0.5 )
            
            self._dirty = True
            
            self.Refresh()
            
            self._media_window.GotoFrame( self._current_frame_index )
            
        elif event.ButtonUp( wx.MOUSE_BTN_ANY ):
            
            if not self._currently_in_a_drag: self._media_window.Play()
            
            self._currently_in_a_drag = False
            
        
    
    def EventPaint( self, event ):
        
        if self._dirty:
            
            self._Redraw()
            
        
        wx.BufferedPaintDC( self, self._canvas_bmp )
        
    
    def EventResize( self, event ):
        
        ( my_width, my_height ) = self.GetClientSize()
        
        ( current_bmp_width, current_bmp_height ) = self._canvas_bmp.GetSize()
        
        if my_width != current_bmp_width or my_height != current_bmp_height:
            
            if my_width > 0 and my_height > 0:
                
                wx.CallAfter( self._canvas_bmp.Destroy )
                
                self._canvas_bmp = wx.EmptyBitmap( my_width, my_height, 24 )
                
                self._dirty = True
                
                self.Refresh()
                
            
        
    
    def GotoFrame( self, frame_index ):
        
        self._current_frame_index = frame_index
        
        self._dirty = True
        
        self.Refresh()
        
        
    
    def TIMEREventUpdate( self, event ):
        
        if self.IsShown():
            
            if self._media.GetMime() == HC.APPLICATION_FLASH:
                
                try:
                    
                    frame_index = self._media_window.CurrentFrame()
                    
                except AttributeError:
                    
                    text = 'The flash window produced an unusual error that probably means it never initialised properly. This is usually because Flash has not been installed for Internet Explorer. '
                    text += os.linesep * 2
                    text += 'Please close the client, open Internet Explorer, and install flash from Adobe\'s site and then try again. If that does not work, please tell the hydrus developer.'
                    
                    HydrusData.ShowText( text )
                    
                    self._timer_update.Stop()
                    
                    raise
                    
                
                if frame_index != self._current_frame_index:
                    
                    self._current_frame_index = frame_index
                    
                    self._dirty = True
                    
                    self.Refresh()
                    
                
            
        
    
class Canvas( object ):
    
    def __init__( self, file_service_key, image_cache, claim_focus = True ):
        
        self._file_service_key = file_service_key
        self._image_cache = image_cache
        self._claim_focus = claim_focus
        
        self._file_service = wx.GetApp().GetManager( 'services' ).GetService( self._file_service_key )
        
        self._canvas_key = os.urandom( 32 )
        
        self._dirty = True
        self._closing = False
        
        self._service_keys_to_services = {}
        
        self._focus_holder = wx.Window( self )
        self._focus_holder.Hide()
        self._focus_holder.SetEventHandler( self )
        
        self._current_media = None
        self._current_display_media = None
        self._media_container = None
        self._current_zoom = 1.0
        self._canvas_zoom = 1.0
        
        self._last_drag_coordinates = None
        self._total_drag_delta = ( 0, 0 )
        
        self.SetBackgroundColour( wx.Colour( *HC.options[ 'gui_colours' ][ 'media_background' ] ) )
        
        self._canvas_bmp = wx.EmptyBitmap( 0, 0, 24 )
        
        self.Bind( wx.EVT_SIZE, self.EventResize )
        
        self.Bind( wx.EVT_PAINT, self.EventPaint )
        self.Bind( wx.EVT_ERASE_BACKGROUND, self.EventEraseBackground )
        
        HydrusGlobals.pubsub.sub( self, 'ZoomIn', 'canvas_zoom_in' )
        HydrusGlobals.pubsub.sub( self, 'ZoomOut', 'canvas_zoom_out' )
        HydrusGlobals.pubsub.sub( self, 'ZoomSwitch', 'canvas_zoom_switch' )
        
    
    def _Archive( self ): wx.GetApp().Write( 'content_updates', { CC.LOCAL_FILE_SERVICE_KEY : [ HydrusData.ContentUpdate( HC.CONTENT_DATA_TYPE_FILES, HC.CONTENT_UPDATE_ARCHIVE, ( self._current_display_media.GetHash(), ) ) ] } )
    
    def _CopyHashToClipboard( self ):
        
        hex_hash = self._current_display_media.GetHash().encode( 'hex' )
        
        HydrusGlobals.pubsub.pub( 'clipboard', 'text', hex_hash )
        
    
    def _CopyLocalUrlToClipboard( self ):
        
        local_url = 'http://127.0.0.1:' + str( HC.options[ 'local_port' ] ) + '/file?hash=' + self._current_display_media.GetHash().encode( 'hex' )
        
        HydrusGlobals.pubsub.pub( 'clipboard', 'text', local_url )
        
    
    def _CopyPathToClipboard( self ):
        
        path = ClientFiles.GetFilePath( self._current_display_media.GetHash(), self._current_display_media.GetMime() )
        
        HydrusGlobals.pubsub.pub( 'clipboard', 'text', path )
        
    
    def _Delete( self ):
        
        with ClientGUIDialogs.DialogYesNo( self, 'Delete this file from the database?' ) as dlg:
            
            if dlg.ShowModal() == wx.ID_YES: wx.GetApp().Write( 'content_updates', { CC.LOCAL_FILE_SERVICE_KEY : [ HydrusData.ContentUpdate( HC.CONTENT_DATA_TYPE_FILES, HC.CONTENT_UPDATE_DELETE, ( self._current_display_media.GetHash(), ) ) ] } )
            
        
        self.SetFocus() # annoying bug because of the modal dialog
        
    
    def _DrawBackgroundBitmap( self ):
        
        dc = wx.MemoryDC( self._canvas_bmp )
        
        dc.SetBackground( wx.Brush( wx.Colour( *HC.options[ 'gui_colours' ][ 'media_background' ] ) ) )
        
        dc.Clear()
        
        self._DrawBackgroundDetails( dc )
        
        self._dirty = False
        
    
    def _DrawBackgroundDetails( self, dc ): pass
    
    def _DrawCurrentMedia( self ):
        
        ( my_width, my_height ) = self.GetClientSize()
        
        if my_width > 0 and my_height > 0:
            
            if self._current_media is not None: self._SizeAndPositionMediaContainer()
            
        
    
    def _GetIndexString( self ): return ''
    
    def _GetMediaContainerSizeAndPosition( self ):
        
        ( my_width, my_height ) = self.GetClientSize()
        
        ( media_width, media_height ) = CalculateMediaContainerSize( self._current_display_media, self._current_zoom )
        
        ( drag_x, drag_y ) = self._total_drag_delta
        
        x_offset = ( my_width - media_width ) / 2 + drag_x
        y_offset = ( my_height - media_height ) / 2 + drag_y
        
        new_size = ( media_width, media_height )
        new_position = ( x_offset, y_offset )
        
        return ( new_size, new_position )
        
    
    def _HydrusShouldNotProcessInput( self ):
        
        if self._current_display_media.GetMime() in EMBED_BUTTON_MIMES:
            
            if self.MouseIsOverMedia(): return True
            
        
        return False
        
    
    def _Inbox( self ): wx.GetApp().Write( 'content_updates', { CC.LOCAL_FILE_SERVICE_KEY : [ HydrusData.ContentUpdate( HC.CONTENT_DATA_TYPE_FILES, HC.CONTENT_UPDATE_INBOX, ( self._current_display_media.GetHash(), ) ) ] } )
    
    def _ManageRatings( self ):
        
        if self._current_media is not None:
            
            with ClientGUIDialogsManage.DialogManageRatings( self, ( self._current_display_media, ) ) as dlg: dlg.ShowModal()
            
        
    
    def _ManageTags( self ):
        
        if self._current_display_media is not None:
            
            with ClientGUIDialogsManage.DialogManageTags( self, self._file_service_key, ( self._current_display_media, ), canvas_key = self._canvas_key ) as dlg: dlg.ShowModal()
            
        
    
    def _OpenExternally( self ):
        
        if self._current_display_media is not None:
            
            hash = self._current_display_media.GetHash()
            mime = self._current_display_media.GetMime()
            
            path = ClientFiles.GetFilePath( hash, mime )
            
            HydrusFileHandling.LaunchFile( path )
            
        
    
    def _PrefetchNeighbours( self ): pass
    
    def _RecalcZoom( self ):
        
        if self._current_display_media is None: self._current_zoom = 1.0
        else:
            
            ( my_width, my_height ) = self.GetClientSize()
            
            ( media_width, media_height ) = self._current_display_media.GetResolution()
            
            self._canvas_zoom = CalculateCanvasZoom( self._current_display_media, ( my_width, my_height ) )
            
            media_needs_to_be_scaled_down = media_width > my_width or media_height > my_height
            media_needs_to_be_scaled_up = media_width < my_width and media_height < my_height and HC.options[ 'fit_to_canvas' ]
            
            if media_needs_to_be_scaled_down or media_needs_to_be_scaled_up: self._current_zoom = self._canvas_zoom
            else: self._current_zoom = 1.0
            
        
        HydrusGlobals.pubsub.pub( 'canvas_new_zoom', self._canvas_key, self._current_zoom )
        
    
    def _SetDirty( self ):
        
        self._dirty = True
        
        self.Refresh()
        
    
    def _SizeAndPositionMediaContainer( self ):
        
        ( new_size, new_position ) = self._GetMediaContainerSizeAndPosition()
        
        if new_size != self._media_container.GetSize(): self._media_container.SetSize( new_size )
        
        if HC.PLATFORM_OSX and new_position == self._media_container.GetPosition(): self._media_container.Refresh()
        
        if new_position != self._media_container.GetPosition(): self._media_container.SetPosition( new_position )
        
    
    def _ZoomIn( self ):
        
        if self._current_display_media is not None:
            
            if self._current_display_media.GetMime() in NON_ZOOMABLE_MIMES: return
            
            my_zoomins = list( ZOOMINS )
            my_zoomins.append( self._canvas_zoom )
            
            my_zoomins.sort()
            
            for zoom in my_zoomins:
                
                if self._current_zoom < zoom:
                    
                    if self._current_display_media.GetMime() in EMBED_BUTTON_MIMES:
                        
                        # because of the event passing under mouse, we want to preserve whitespace around flash
                        
                        ( my_width, my_height ) = self.GetClientSize()
                        
                        ( new_media_width, new_media_height ) = CalculateMediaContainerSize( self._current_display_media, zoom )
                        
                        if new_media_width >= my_width or new_media_height >= my_height: return
                        
                    
                    ( drag_x, drag_y ) = self._total_drag_delta
                    
                    zoom_ratio = zoom / self._current_zoom
                    
                    self._total_drag_delta = ( int( drag_x * zoom_ratio ), int( drag_y * zoom_ratio ) )
                    
                    self._current_zoom = zoom
                    
                    HydrusGlobals.pubsub.pub( 'canvas_new_zoom', self._canvas_key, self._current_zoom )
                    
                    self._SetDirty()
                    
                    break
                    
                
            
        
    
    def _ZoomOut( self ):
        
        if self._current_display_media is not None:
            
            if self._current_display_media.GetMime() in NON_ZOOMABLE_MIMES: return
            
            my_zoomouts = list( ZOOMOUTS )
            my_zoomouts.append( self._canvas_zoom )
            
            my_zoomouts.sort( reverse = True )
            
            for zoom in my_zoomouts:
                
                if self._current_zoom > zoom:
                    
                    ( drag_x, drag_y ) = self._total_drag_delta
                    
                    zoom_ratio = zoom / self._current_zoom
                    
                    self._total_drag_delta = ( int( drag_x * zoom_ratio ), int( drag_y * zoom_ratio ) )
                    
                    self._current_zoom = zoom
                    
                    HydrusGlobals.pubsub.pub( 'canvas_new_zoom', self._canvas_key, self._current_zoom )
                    
                    self._SetDirty()
                    
                    break
                    
                
            
        
    
    def _ZoomSwitch( self ):
        
        ( my_width, my_height ) = self.GetClientSize()
        
        ( media_width, media_height ) = self._current_display_media.GetResolution()
        
        if self._current_display_media.GetMime() not in EMBED_BUTTON_MIMES:
            
            if self._current_zoom == 1.0: new_zoom = self._canvas_zoom
            else: new_zoom = 1.0
            
            if new_zoom != self._current_zoom:
                
                ( drag_x, drag_y ) = self._total_drag_delta
                
                zoom_ratio = new_zoom / self._current_zoom
                
                self._total_drag_delta = ( int( drag_x * zoom_ratio ), int( drag_y * zoom_ratio ) )
                
                self._current_zoom = new_zoom
                
                HydrusGlobals.pubsub.pub( 'canvas_new_zoom', self._canvas_key, self._current_zoom )
                
                self._SetDirty()
                
            
        
    
    def EventEraseBackground( self, event ): pass
    
    def EventPaint( self, event ):
        
        if self._dirty:
            
            self._DrawBackgroundBitmap()
            
            if self._media_container is not None:
                
                self._DrawCurrentMedia()
                
            
        
        wx.BufferedPaintDC( self, self._canvas_bmp )
        
    
    def EventResize( self, event ):
        
        if not self._closing:
            
            ( my_width, my_height ) = self.GetClientSize()
            
            wx.CallAfter( self._canvas_bmp.Destroy )
            
            self._canvas_bmp = wx.EmptyBitmap( my_width, my_height, 24 )
            
            if self._media_container is not None:
                
                ( media_width, media_height ) = self._media_container.GetClientSize()
                
                if my_width != media_width or my_height != media_height:
                    
                    self._RecalcZoom()
                    
                
            
            self._SetDirty()
            
        
        event.Skip()
        
    
    def KeepCursorAlive( self ): pass
    
    def MouseIsOverMedia( self ):
        
        ( x, y ) = self._media_container.GetPosition()
        ( width, height ) = self._media_container.GetSize()
        
        ( mouse_x, mouse_y ) = self.ScreenToClient( wx.GetMousePosition() )
        
        if mouse_x >= x and mouse_x <= x + width and mouse_y >= y and mouse_y <= y + height: return True
        
        return False
        
    
    def SetMedia( self, media ):
        
        initial_image = self._current_media == None
        
        if media != self._current_media:
            
            wx.GetApp().ResetIdleTimer()
            
            with wx.FrozenWindow( self ):
                
                self._current_media = media
                self._current_display_media = None
                self._total_drag_delta = ( 0, 0 )
                self._last_drag_coordinates = None
                
                if self._media_container is not None:
                    
                    self._media_container.Hide()
                    
                    wx.CallAfter( self._media_container.Destroy )
                    
                    self._media_container = None
                    
                
                if self._current_media is not None:
                    
                    self._current_display_media = self._current_media.GetDisplayMedia()
                    
                    if self._current_display_media.GetLocationsManager().HasLocal():
                        
                        self._RecalcZoom()
                        
                        ( initial_size, initial_position ) = self._GetMediaContainerSizeAndPosition()
                        
                        self._media_container = MediaContainer( self, self._image_cache, self._current_display_media, initial_size, initial_position )
                        
                        if self._claim_focus: self._media_container.SetFocus()
                        
                        self._PrefetchNeighbours()
                        
                    else: self._current_media = None
                    
                
                HydrusGlobals.pubsub.pub( 'canvas_new_display_media', self._canvas_key, self._current_display_media )
                HydrusGlobals.pubsub.pub( 'canvas_new_index_string', self._canvas_key, self._GetIndexString() )
                
                self._SetDirty()
                
            
        
    
    def ZoomIn( self, canvas_key ):
        
        if canvas_key == self._canvas_key:
            
            self._ZoomIn()
            
        
    
    def ZoomOut( self, canvas_key ):
        
        if canvas_key == self._canvas_key:
            
            self._ZoomOut()
            
        
    
    def ZoomSwitch( self, canvas_key ):
        
        if canvas_key == self._canvas_key:
            
            self._ZoomSwitch()
            
        
    
class CanvasWithDetails( Canvas ):
    
    def __init__( self, *args, **kwargs ):
        
        Canvas.__init__( self, *args, **kwargs )
        
        self._hover_commands = ClientGUIHoverFrames.FullscreenHoverFrameCommands( self, self._canvas_key )
        self._hover_tags = ClientGUIHoverFrames.FullscreenHoverFrameTags( self, self._canvas_key )
        
        ratings_services = wx.GetApp().GetManager( 'services' ).GetServices( ( HC.RATINGS_SERVICES ) )
        
        if len( ratings_services ) > 0: self._hover_ratings = ClientGUIHoverFrames.FullscreenHoverFrameRatings( self, self._canvas_key )
        
    
    def _DrawBackgroundDetails( self, dc ):
        
        if self._current_media is not None:
            
            ( client_width, client_height ) = self.GetClientSize()
            
            # tags on the top left
            
            dc.SetFont( wx.SystemSettings.GetFont( wx.SYS_DEFAULT_GUI_FONT ) )
            
            tags_manager = self._current_media.GetDisplayMedia().GetTagsManager()
            
            siblings_manager = wx.GetApp().GetManager( 'tag_siblings' )
            
            current = siblings_manager.CollapseTags( tags_manager.GetCurrent() )
            pending = siblings_manager.CollapseTags( tags_manager.GetPending() )
            
            tags_i_want_to_display = list( current.union( pending ) )
            
            tags_i_want_to_display.sort()
            
            current_y = 3
            
            namespace_colours = HC.options[ 'namespace_colours' ]
            
            for tag in tags_i_want_to_display:
                
                if tag in current: display_string = tag
                elif tag in pending: display_string = '(+) ' + tag
                
                if ':' in tag:
                    
                    ( namespace, sub_tag ) = tag.split( ':', 1 )
                    
                    if namespace in namespace_colours: ( r, g, b ) = namespace_colours[ namespace ]
                    else: ( r, g, b ) = namespace_colours[ None ]
                    
                else: ( r, g, b ) = namespace_colours[ '' ]
                
                dc.SetTextForeground( wx.Colour( r, g, b ) )
                
                ( x, y ) = dc.GetTextExtent( display_string )
                
                dc.DrawText( display_string, 5, current_y )
                
                current_y += y
                
            
            dc.SetTextForeground( wx.Colour( *HC.options[ 'gui_colours' ][ 'media_text' ] ) )
            
            # top right
            
            current_y = 2
            
            # icons
            
            icons_to_show = []
            
            if self._current_media.HasInbox():
                
                dc.DrawBitmap( CC.GlobalBMPs.inbox_bmp, client_width - 18, 2 )
                
                current_y += 18
                
            
            # repo strings
            
            file_repo_strings = self._current_media.GetLocationsManager().GetFileRepositoryStrings()
            
            for file_repo_string in file_repo_strings:
                
                ( text_width, text_height ) = dc.GetTextExtent( file_repo_string )
                
                dc.DrawText( file_repo_string, client_width - text_width - 3, current_y )
                
                current_y += text_height + 4
                
            
            # ratings
            
            ( local_ratings, remote_ratings ) = self._current_display_media.GetRatings()
            
            services_manager = wx.GetApp().GetManager( 'services' )
            
            like_services = services_manager.GetServices( ( HC.LOCAL_RATING_LIKE, ) )
            
            like_services.reverse()
            
            like_rating_current_x = client_width - 16
            
            for like_service in like_services:
                
                service_key = like_service.GetServiceKey()
                
                rating_state = ClientRatings.GetLikeStateFromMedia( ( self._current_display_media, ), service_key )
                
                ClientRatings.DrawLike( dc, like_rating_current_x, current_y, service_key, rating_state )
                
                like_rating_current_x -= 16
                
            
            if len( like_services ) > 0: current_y += 20
            
            
            numerical_services = services_manager.GetServices( ( HC.LOCAL_RATING_NUMERICAL, ) )
            
            for numerical_service in numerical_services:
                
                service_key = numerical_service.GetServiceKey()
                
                ( rating_state, rating ) = ClientRatings.GetNumericalStateFromMedia( ( self._current_display_media, ), service_key )
                
                numerical_width = ClientRatings.GetNumericalWidth( service_key )
                
                ClientRatings.DrawNumerical( dc, client_width - numerical_width, current_y, service_key, rating_state, rating )
                
                current_y += 20
                
            
            # middle
            
            current_y = 3
            
            title_string = self._current_display_media.GetTitleString()
            
            if len( title_string ) > 0:
                
                ( x, y ) = dc.GetTextExtent( title_string )
                
                dc.DrawText( title_string, ( client_width - x ) / 2, current_y )
                
                current_y += y + 3
                
            
            info_string = self._GetInfoString()
            
            ( x, y ) = dc.GetTextExtent( info_string )
            
            dc.DrawText( info_string, ( client_width - x ) / 2, current_y )
            
            index_string = self._GetIndexString()
            
            if len( index_string ) > 0:
                
                ( x, y ) = dc.GetTextExtent( index_string )
                
                dc.DrawText( index_string, client_width - x - 3, client_height - y - 3 )
                
            
        
    
class CanvasPanel( Canvas, wx.Window ):
    
    def __init__( self, parent, page_key, file_service_key ):
        
        wx.Window.__init__( self, parent, style = wx.SIMPLE_BORDER )
        Canvas.__init__( self, file_service_key, wx.GetApp().GetCache( 'preview' ), claim_focus = False )
        
        self._page_key = page_key
        
        HydrusGlobals.pubsub.sub( self, 'FocusChanged', 'focus_changed' )
        HydrusGlobals.pubsub.sub( self, 'ProcessContentUpdates', 'content_updates_gui' )
        
        self.Bind( wx.EVT_RIGHT_DOWN, self.EventShowMenu )
        
        self.Bind( wx.EVT_MENU, self.EventMenu )
        
        wx.CallAfter( self.Refresh )
        
    
    def EventMenu( self, event ):
        
        # is None bit means this is prob from a keydown->menu event
        if event.GetEventObject() is None and self._HydrusShouldNotProcessInput(): event.Skip()
        else:
            
            action = ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetAction( event.GetId() )
            
            if action is not None:
                
                ( command, data ) = action
                
                if command == 'archive': self._Archive()
                elif command == 'copy_files':
                    with wx.BusyCursor(): wx.GetApp().Write( 'copy_files', ( self._current_display_media.GetHash(), ) )
                elif command == 'copy_hash': self._CopyHashToClipboard()
                elif command == 'copy_local_url': self._CopyLocalUrlToClipboard()
                elif command == 'copy_path': self._CopyPathToClipboard()
                elif command == 'delete': self._Delete()
                elif command == 'inbox': self._Inbox()
                elif command == 'manage_ratings': self._ManageRatings()
                elif command == 'manage_tags': wx.CallAfter( self._ManageTags )
                elif command == 'open_externally': self._OpenExternally()
                else: event.Skip()
                
            
        
    
    def EventShowMenu( self, event ):
        
        if self._current_display_media is not None:
            
            services = wx.GetApp().GetManager( 'services' ).GetServices()
            
            local_ratings_services = [ service for service in services if service.GetServiceType() in ( HC.LOCAL_RATING_LIKE, HC.LOCAL_RATING_NUMERICAL ) ]
            
            i_can_post_ratings = len( local_ratings_services ) > 0
            
            menu = wx.Menu()
            
            menu.Append( CC.ID_NULL, self._current_display_media.GetPrettyInfo() )
            menu.Append( CC.ID_NULL, self._current_display_media.GetPrettyAge() )
            
            #
            
            menu.AppendSeparator()
            
            manage_menu = wx.Menu()
            
            manage_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'manage_tags' ), 'tags' )
            
            if i_can_post_ratings: manage_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'manage_ratings' ), 'ratings' )
            
            menu.AppendMenu( CC.ID_NULL, 'manage', manage_menu )
            
            menu.AppendSeparator()
            
            if self._current_display_media.HasInbox(): menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'archive' ), '&archive' )
            if self._current_display_media.HasArchive(): menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'inbox' ), 'return to &inbox' )
            menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'delete', CC.LOCAL_FILE_SERVICE_KEY ), '&delete' )
            
            menu.AppendSeparator()
            
            menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'open_externally', CC.LOCAL_FILE_SERVICE_KEY ), '&open externally' )
            
            share_menu = wx.Menu()
            
            copy_menu = wx.Menu()
            
            copy_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'copy_files' ), 'file' )
            copy_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'copy_hash' ), 'hash' )
            copy_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'copy_path' ), 'path' )
            copy_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'copy_local_url' ), 'local url' )
            
            share_menu.AppendMenu( CC.ID_NULL, 'copy', copy_menu )
            
            menu.AppendMenu( CC.ID_NULL, 'share', share_menu )
            
            self.PopupMenu( menu )
            
            self._menu_open = False
            
            wx.CallAfter( menu.Destroy )
            
            event.Skip()
            
        
    
    def FocusChanged( self, page_key, media ):
        
        if page_key == self._page_key: self.SetMedia( media )
        
    
    def ProcessContentUpdates( self, service_keys_to_content_updates ):
        
        if self._current_display_media is not None:
            
            my_hash = self._current_display_media.GetHash()
            
            do_redraw = False
            
            for ( service_key, content_updates ) in service_keys_to_content_updates.items():
                
                if True in ( my_hash in content_update.GetHashes() for content_update in content_updates ):
                    
                    do_redraw = True
                    
                    break
                    
                
            
            if do_redraw:
                
                self._SetDirty()
                
            
        
    
class CanvasFullscreenMediaList( ClientMedia.ListeningMediaList, CanvasWithDetails, ClientGUICommon.FrameThatResizes ):
    
    def __init__( self, my_parent, page_key, file_service_key, media_results ):
        
        ClientGUICommon.FrameThatResizes.__init__( self, my_parent, resize_option_prefix = 'fs_', title = 'hydrus client fullscreen media viewer' )
        CanvasWithDetails.__init__( self, file_service_key, wx.GetApp().GetCache( 'fullscreen' ) )
        ClientMedia.ListeningMediaList.__init__( self, file_service_key, media_results )
        
        self._page_key = page_key
        
        self._menu_open = False
        
        self._just_started = True
        
        self.Show( True )
        
        wx.GetApp().SetTopWindow( self )
        
        self._timer_cursor_hide = wx.Timer( self, id = ID_TIMER_CURSOR_HIDE )
        
        self.Bind( wx.EVT_TIMER, self.TIMEREventCursorHide, id = ID_TIMER_CURSOR_HIDE )
        
        self.Bind( wx.EVT_CLOSE, self.EventClose )
        
        self.Bind( wx.EVT_MOTION, self.EventDrag )
        self.Bind( wx.EVT_LEFT_DOWN, self.EventDragBegin )
        self.Bind( wx.EVT_LEFT_UP, self.EventDragEnd )
        
        HydrusGlobals.pubsub.pub( 'set_focus', self._page_key, None )
        
        HydrusGlobals.pubsub.sub( self, 'Close', 'canvas_close' )
        HydrusGlobals.pubsub.sub( self, 'FullscreenSwitch', 'canvas_fullscreen_switch' )
        
    
    def _Close( self ):
        
        self._closing = True
        
        HydrusGlobals.pubsub.pub( 'set_focus', self._page_key, self._current_media )
        
        if HC.PLATFORM_OSX and self.IsFullScreen(): self.ShowFullScreen( False, wx.FULLSCREEN_ALL )
        
        wx.CallAfter( self.Destroy )
        
    
    def _DoManualPan( self, delta_x, delta_y ):
        
        ( old_delta_x, old_delta_y ) = self._total_drag_delta
        
        self._total_drag_delta = ( old_delta_x + delta_x, old_delta_y + delta_y )
        
        self._DrawCurrentMedia()
        
    
    def _FullscreenSwitch( self ):
        
        if self.IsFullScreen(): self.ShowFullScreen( False, wx.FULLSCREEN_ALL )
        else: self.ShowFullScreen( True, wx.FULLSCREEN_ALL )
        
    
    def _GetInfoString( self ):
        
        info_string = self._current_media.GetPrettyInfo() + ' | ' + HydrusData.ConvertZoomToPercentage( self._current_zoom ) + ' | ' + self._current_media.GetPrettyAge()
        
        return info_string
        
    
    def _GetIndexString( self ):
        
        index_string = HydrusData.ConvertValueRangeToPrettyString( self._sorted_media.index( self._current_media ) + 1, len( self._sorted_media ) )
        
        return index_string
        
    
    def _PrefetchNeighbours( self ):
        
        media_looked_at = set()
        
        to_render = []
        
        previous = self._current_media
        next = self._current_media
        
        if self._just_started:
            
            delay_base = 800
            
            num_to_go_back = 2
            num_to_go_forward = 2
            
            self._just_started = False
            
        else:
            
            delay_base = 200
            
            num_to_go_back = 3
            num_to_go_forward = 5
            
        
        # if media_looked_at nukes the list, we want shorter delays, so do next first
        
        for i in range( num_to_go_forward ):
            
            next = self._GetNext( next )
            
            if next in media_looked_at:
                
                break
                
            else:
                
                media_looked_at.add( next )
                
            
            delay = delay_base * ( i + 1 )
            
            to_render.append( ( next, delay ) )
            
        
        for i in range( num_to_go_back ):
            
            previous = self._GetPrevious( previous )
            
            if previous in media_looked_at:
                
                break
                
            else:
                
                media_looked_at.add( previous )
                
            
            delay = delay_base * 2 * ( i + 1 )
            
            to_render.append( ( previous, delay ) )
            
        
        ( my_width, my_height ) = self.GetClientSize()
        
        for ( media, delay ) in to_render:
            
            hash = media.GetHash()
            
            if media.GetMime() in ( HC.IMAGE_JPEG, HC.IMAGE_PNG ):
                
                ( media_width, media_height ) = media.GetResolution()
                
                if media_width > my_width or media_height > my_height: zoom = CalculateCanvasZoom( media, ( my_width, my_height ) )
                else: zoom = 1.0
                
                resolution_to_request = ( int( round( zoom * media_width ) ), int( round( zoom * media_height ) ) )
                
                if not self._image_cache.HasImage( hash, resolution_to_request ): wx.CallLater( delay, self._image_cache.GetImage, media, resolution_to_request )
                
            
        
    
    def _Remove( self ):
        
        next_media = self._GetNext( self._current_media )
        
        if next_media == self._current_media: next_media = None
        
        hashes = { self._current_display_media.GetHash() }
        
        HydrusGlobals.pubsub.pub( 'remove_media', self._page_key, hashes )
        
        singleton_media = { self._current_display_media }
        
        ClientMedia.ListeningMediaList._RemoveMedia( self, singleton_media, {} )
        
        if self.HasNoMedia(): self._Close()
        elif self.HasMedia( self._current_media ):
            
            HydrusGlobals.pubsub.pub( 'canvas_new_index_string', self._canvas_key, self._GetIndexString() )
            
            self._SetDirty()
            
        else: self.SetMedia( next_media )
        
    
    def _ShowFirst( self ): self.SetMedia( self._GetFirst() )
    
    def _ShowLast( self ): self.SetMedia( self._GetLast() )
    
    def _ShowNext( self ): self.SetMedia( self._GetNext( self._current_media ) )
    
    def _ShowPrevious( self ): self.SetMedia( self._GetPrevious( self._current_media ) )
    
    def _StartSlideshow( self, interval ): pass
    
    def AddMediaResults( self, page_key, media_results ):
        
        if page_key == self._page_key:
            
            ClientMedia.ListeningMediaList.AddMediaResults( self, media_results )
            
            HydrusGlobals.pubsub.pub( 'canvas_new_index_string', self._canvas_key, self._GetIndexString() )
            
            self._SetDirty()
            
        
    
    def Close( self, canvas_key ):
        
        if canvas_key == self._canvas_key:
            
            self._Close()
            
        
    
    def EventClose( self, event ):
        
        self._Close()
        
    
    def EventDrag( self, event ):
        
        CC.CAN_HIDE_MOUSE = True
        
        self._focus_holder.SetFocus()
        
        if event.Dragging() and self._last_drag_coordinates is not None:
            
            ( old_x, old_y ) = self._last_drag_coordinates
            
            ( x, y ) = event.GetPosition()
            
            ( delta_x, delta_y ) = ( x - old_x, y - old_y )
            
            if HC.PLATFORM_WINDOWS: self.WarpPointer( old_x, old_y )
            else: self._last_drag_coordinates = ( x, y )
            
            ( old_delta_x, old_delta_y ) = self._total_drag_delta
            
            self._total_drag_delta = ( old_delta_x + delta_x, old_delta_y + delta_y )
            
            self._DrawCurrentMedia()
            
        
        self.SetCursor( wx.StockCursor( wx.CURSOR_ARROW ) )
        
        self._timer_cursor_hide.Start( 800, wx.TIMER_ONE_SHOT )
        
    
    def EventDragBegin( self, event ):
        
        ( x, y ) = event.GetPosition()
        
        ( client_x, client_y ) = self.GetClientSize()
        
        if self._current_display_media.GetMime() not in EMBED_BUTTON_MIMES: # to stop warping over flash
            
            if x < 20 or x > client_x - 20 or y < 20 or y > client_y -20:
                
                better_x = x
                better_y = y
                
                if x < 20: better_x = 20
                if y < 20: better_y = 20
                
                if x > client_x - 20: better_x = client_x - 20
                if y > client_y - 20: better_y = client_y - 20
                
                if HC.PLATFORM_WINDOWS:
                    
                    self.WarpPointer( better_x, better_y )
                    
                    x = better_x
                    y = better_y
                    
                
            
        
        self._last_drag_coordinates = ( x, y )
        
        event.Skip()
        
    
    def EventDragEnd( self, event ):
        
        self._last_drag_coordinates = None
        
        event.Skip()
        
    
    def EventFullscreenSwitch( self, event ): self._FullscreenSwitch()
    
    def FullscreenSwitch( self, canvas_key ):
        
        if canvas_key == self._canvas_key:
            
            self._FullscreenSwitch()
            
        
    
    def KeepCursorAlive( self ): self._timer_cursor_hide.Start( 800, wx.TIMER_ONE_SHOT )
    
    def ProcessContentUpdates( self, service_keys_to_content_updates ):
        
        next_media = self._GetNext( self._current_media )
        
        if next_media == self._current_media: next_media = None
        
        ClientMedia.ListeningMediaList.ProcessContentUpdates( self, service_keys_to_content_updates )
        
        if self.HasNoMedia(): self._Close()
        elif self.HasMedia( self._current_media ):
            
            HydrusGlobals.pubsub.pub( 'canvas_new_index_string', self._canvas_key, self._GetIndexString() )
            
            self._SetDirty()
            
        else: self.SetMedia( next_media )
        
    
    def TIMEREventCursorHide( self, event ):
        
        if not CC.CAN_HIDE_MOUSE: return
        
        if self._menu_open: self._timer_cursor_hide.Start( 800, wx.TIMER_ONE_SHOT )
        else: self.SetCursor( wx.StockCursor( wx.CURSOR_BLANK ) )
        
    
class CanvasFullscreenMediaListFilter( CanvasFullscreenMediaList ):
    
    def __init__( self, my_parent, page_key, file_service_key, media_results ):
        
        CanvasFullscreenMediaList.__init__( self, my_parent, page_key, file_service_key, media_results )
        
        self._kept = set()
        self._deleted = set()
        
        self.Bind( wx.EVT_LEFT_DOWN, self.EventMouseKeep )
        self.Bind( wx.EVT_LEFT_DCLICK, self.EventMouseKeep )
        self.Bind( wx.EVT_MIDDLE_DOWN, self.EventBack )
        self.Bind( wx.EVT_MIDDLE_DCLICK, self.EventBack )
        self.Bind( wx.EVT_MOUSEWHEEL, self.EventMouseWheel )
        self.Bind( wx.EVT_RIGHT_DOWN, self.EventDelete )
        self.Bind( wx.EVT_RIGHT_DCLICK, self.EventDelete )
        
        self.Bind( wx.EVT_MENU, self.EventMenu )
        
        self.Bind( wx.EVT_CHAR_HOOK, self.EventCharHook )
        
        self.SetMedia( self._GetFirst() )
        
    
    def _Back( self ):
        
        if not self._HydrusShouldNotProcessInput():
            
            if self._current_media == self._GetFirst(): return
            else:
                
                self._ShowPrevious()
                
                self._kept.discard( self._current_media )
                self._deleted.discard( self._current_media )
                
            
        
    
    def _Close( self ):
        
        if not self._HydrusShouldNotProcessInput():
            
            if len( self._kept ) > 0 or len( self._deleted ) > 0:
                
                with ClientGUIDialogs.DialogFinishFiltering( self, len( self._kept ), len( self._deleted ) ) as dlg:
                    
                    modal = dlg.ShowModal()
                    
                    if modal == wx.ID_CANCEL:
                        
                        if self._current_media in self._kept: self._kept.remove( self._current_media )
                        if self._current_media in self._deleted: self._deleted.remove( self._current_media )
                        
                    else:
                        
                        if modal == wx.ID_YES:
                            
                            self._deleted_hashes = [ media.GetHash() for media in self._deleted ]
                            self._kept_hashes = [ media.GetHash() for media in self._kept ]
                            
                            content_updates = []
                            
                            content_updates.append( HydrusData.ContentUpdate( HC.CONTENT_DATA_TYPE_FILES, HC.CONTENT_UPDATE_DELETE, self._deleted_hashes ) )
                            content_updates.append( HydrusData.ContentUpdate( HC.CONTENT_DATA_TYPE_FILES, HC.CONTENT_UPDATE_ARCHIVE, self._kept_hashes ) )
                            
                            wx.GetApp().Write( 'content_updates', { CC.LOCAL_FILE_SERVICE_KEY : content_updates } )
                            
                            self._kept = set()
                            self._deleted = set()
                            
                            self._current_media = self._GetFirst() # so the pubsub on close is better
                            
                        
                        CanvasFullscreenMediaList._Close( self )
                        
                    
                
            else: CanvasFullscreenMediaList._Close( self )
            
        
    
    def _Delete( self ):
        
        self._deleted.add( self._current_media )
        
        if self._current_media == self._GetLast(): self._Close()
        else: self._ShowNext()
        
    
    def _Keep( self ):
        
        self._kept.add( self._current_media )
        
        if self._current_media == self._GetLast(): self._Close()
        else: self._ShowNext()
        
    
    def _Skip( self ):
        
        if not self._HydrusShouldNotProcessInput():
            
            if self._current_media == self._GetLast(): self._Close()
            else: self._ShowNext()
            
        
    
    def Keep( self, canvas_key ):
        
        if canvas_key == self._canvas_key:
            
            self._Keep()
            
        
    
    def Back( self, canvas_key ):
        
        if canvas_key == self._canvas_key:
            
            self._Back()
            
        
    
    def Delete( self, canvas_key ):
        
        if canvas_key == self._canvas_key:
            
            self._Delete()
            
        
    
    def EventBack( self, event ):
        
        self._Back()
        
    
    def EventButtonBack( self, event ): self.EventBack( event )
    def EventButtonDelete( self, event ): self._Delete()
    def EventButtonDone( self, event ): self._Close()
    def EventButtonKeep( self, event ): self._Keep()
    def EventButtonSkip( self, event ):
        
        if self._current_media == self._GetLast(): self._Close()
        else: self._ShowNext()
        
    
    def EventCharHook( self, event ):
        
        if self._HydrusShouldNotProcessInput(): event.Skip()
        else:
        
            ( modifier, key ) = ClientData.GetShortcutFromEvent( event )
            
            if modifier == wx.ACCEL_NORMAL and key == wx.WXK_SPACE: self._Keep()
            elif modifier == wx.ACCEL_NORMAL and key in ( ord( '+' ), wx.WXK_ADD, wx.WXK_NUMPAD_ADD ): self._ZoomIn()
            elif modifier == wx.ACCEL_NORMAL and key in ( ord( '-' ), wx.WXK_SUBTRACT, wx.WXK_NUMPAD_SUBTRACT ): self._ZoomOut()
            elif modifier == wx.ACCEL_NORMAL and key == ord( 'Z' ): self._ZoomSwitch()
            elif modifier == wx.ACCEL_NORMAL and key == wx.WXK_BACK: self.EventBack( event )
            elif modifier == wx.ACCEL_NORMAL and key in ( wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER, wx.WXK_ESCAPE ): self._Close()
            elif modifier == wx.ACCEL_NORMAL and key in ( wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE ): self.EventDelete( event )
            elif modifier == wx.ACCEL_CTRL and key == ord( 'C' ):
                with wx.BusyCursor(): wx.GetApp().Write( 'copy_files', ( self._current_display_media.GetHash(), ) )
            elif not event.ShiftDown() and key in ( wx.WXK_UP, wx.WXK_NUMPAD_UP ): self.EventSkip( event )
            else:
                
                key_dict = HC.options[ 'shortcuts' ][ modifier ]
                
                if key in key_dict:
                    
                    action = key_dict[ key ]
                    
                    self.ProcessEvent( wx.CommandEvent( commandType = wx.wxEVT_COMMAND_MENU_SELECTED, winid = ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( action ) ) )
                    
                else: event.Skip()
                
            
        
    
    def EventDelete( self, event ):
        
        if self._HydrusShouldNotProcessInput(): event.Skip()
        else: self._Delete()
        
    
    def EventMouseKeep( self, event ):
        
        if self._HydrusShouldNotProcessInput(): event.Skip()
        else:
            
            if event.ShiftDown(): self.EventDragBegin( event )
            else: self._Keep()
            
        
    
    def EventMenu( self, event ):
        
        if self._HydrusShouldNotProcessInput(): event.Skip()
        else:
            
            action = ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetAction( event.GetId() )
            
            if action is not None:
                
                ( command, data ) = action
                
                if command == 'archive': self._Keep()
                elif command == 'back': self.EventBack( event )
                elif command == 'close': self._Close()
                elif command == 'delete': self.EventDelete( event )
                elif command == 'fullscreen_switch': self._FullscreenSwitch()
                elif command == 'filter': self._Close()
                elif command == 'frame_back': self._media_container.GotoPreviousOrNextFrame( -1 )
                elif command == 'frame_next': self._media_container.GotoPreviousOrNextFrame( 1 )
                elif command == 'manage_ratings': self._ManageRatings()
                elif command == 'manage_tags': wx.CallAfter( self._ManageTags )
                elif command in ( 'pan_up', 'pan_down', 'pan_left', 'pan_right' ):
                    
                    distance = 20
                    
                    if command == 'pan_up': self._DoManualPan( 0, -distance )
                    elif command == 'pan_down': self._DoManualPan( 0, distance )
                    elif command == 'pan_left': self._DoManualPan( -distance, 0 )
                    elif command == 'pan_right': self._DoManualPan( distance, 0 )
                    
                elif command == 'zoom_in': self._ZoomIn()
                elif command == 'zoom_out': self._ZoomOut()
                else: event.Skip()
                
            
        
    
    def EventMouseWheel( self, event ):
        
        if self._HydrusShouldNotProcessInput(): event.Skip()
        else:
            
            if event.CmdDown():
                
                if event.GetWheelRotation() > 0: self._ZoomIn()
                else: self._ZoomOut()
                
            
        
    
    def EventSkip( self, event ):
        
        self._Skip()
        
    
    def Skip( self, canvas_key ):
        
        if canvas_key == self._canvas_key:
            
            self._Skip()
            
        
    
class CanvasFullscreenMediaListFilterInbox( CanvasFullscreenMediaListFilter ):
    
    def __init__( self, my_parent, page_key, file_service_key, media_results ):
        
        CanvasFullscreenMediaListFilter.__init__( self, my_parent, page_key, file_service_key, media_results )
        
        HydrusGlobals.pubsub.sub( self, 'Keep', 'canvas_archive' )
        HydrusGlobals.pubsub.sub( self, 'Delete', 'canvas_delete' )
        HydrusGlobals.pubsub.sub( self, 'Skip', 'canvas_show_next' )
        HydrusGlobals.pubsub.sub( self, 'Back', 'canvas_show_previous' )
        
        self._hover_commands.SetNavigable( False )
        self._hover_commands.SetAlwaysArchive( True )
        
    
class CanvasFullscreenMediaListNavigable( CanvasFullscreenMediaList ):
    
    def __init__( self, my_parent, page_key, file_service_key, media_results ):
        
        CanvasFullscreenMediaList.__init__( self, my_parent, page_key, file_service_key, media_results )
        
        HydrusGlobals.pubsub.sub( self, 'Archive', 'canvas_archive' )
        HydrusGlobals.pubsub.sub( self, 'Delete', 'canvas_delete' )
        HydrusGlobals.pubsub.sub( self, 'Inbox', 'canvas_inbox' )
        HydrusGlobals.pubsub.sub( self, 'ShowFirst', 'canvas_show_first' )
        HydrusGlobals.pubsub.sub( self, 'ShowLast', 'canvas_show_last' )
        HydrusGlobals.pubsub.sub( self, 'ShowNext', 'canvas_show_next' )
        HydrusGlobals.pubsub.sub( self, 'ShowPrevious', 'canvas_show_previous' )
        
        self._hover_commands.SetNavigable( True )
        
    
    def Archive( self, canvas_key ):
        
        if self._canvas_key == canvas_key:
            
            self._Archive()
            
        
    
    def Delete( self, canvas_key ):
        
        if self._canvas_key == canvas_key:
            
            self._Delete()
            
        
    
    def EventArchive( self, event ):
        
        self._Archive()
        
    
    def EventDelete( self, event ):
        
        self._Delete()
        
    
    def EventNext( self, event ):
        
        self._ShowNext()
        
    
    def EventPrevious( self, event ):
        
        self._ShowPrevious()
        
    
    def Inbox( self, canvas_key ):
        
        if self._canvas_key == canvas_key:
            
            self._Inbox()
            
        
    
    def ShowFirst( self, canvas_key ):
        
        if canvas_key == self._canvas_key:
            
            self._ShowFirst()
            
        
    
    def ShowLast( self, canvas_key ):
        
        if canvas_key == self._canvas_key:
            
            self._ShowLast()
            
        
    
    def ShowNext( self, canvas_key ):
        
        if canvas_key == self._canvas_key:
            
            self._ShowNext()
            
        
    
    def ShowPrevious( self, canvas_key ):
        
        if canvas_key == self._canvas_key:
            
            self._ShowPrevious()
            
        
    
class CanvasFullscreenMediaListBrowser( CanvasFullscreenMediaListNavigable ):
    
    def __init__( self, my_parent, page_key, file_service_key, media_results, first_hash ):
        
        CanvasFullscreenMediaListNavigable.__init__( self, my_parent, page_key, file_service_key, media_results )
        
        self._timer_slideshow = wx.Timer( self, id = ID_TIMER_SLIDESHOW )
        
        self.Bind( wx.EVT_TIMER, self.TIMEREventSlideshow, id = ID_TIMER_SLIDESHOW )
        
        self.Bind( wx.EVT_LEFT_DCLICK, self.EventClose )
        self.Bind( wx.EVT_MIDDLE_DOWN, self.EventClose )
        self.Bind( wx.EVT_MOUSEWHEEL, self.EventMouseWheel )
        self.Bind( wx.EVT_RIGHT_DOWN, self.EventShowMenu )
        
        self.Bind( wx.EVT_MENU, self.EventMenu )
        self.Bind( wx.EVT_CHAR_HOOK, self.EventCharHook )
        
        if first_hash is None: self.SetMedia( self._GetFirst() )
        else: self.SetMedia( self._GetMedia( { first_hash } )[0] )
        
        HydrusGlobals.pubsub.sub( self, 'AddMediaResults', 'add_media_results' )
        
    
    def _PausePlaySlideshow( self ):
        
        if self._timer_slideshow.IsRunning(): self._timer_slideshow.Stop()
        elif self._timer_slideshow.GetInterval() > 0: self._timer_slideshow.Start()
        
    
    def _StartSlideshow( self, interval = None ):
        
        self._timer_slideshow.Stop()
        
        if interval is None:
            
            with ClientGUIDialogs.DialogTextEntry( self, 'Enter the interval, in seconds.', default = '15' ) as dlg:
                
                if dlg.ShowModal() == wx.ID_OK:
                    
                    try: interval = int( float( dlg.GetValue() ) * 1000 )
                    except: return
                    
                
            
        
        if interval > 0: self._timer_slideshow.Start( interval, wx.TIMER_CONTINUOUS )
        
    
    def EventCharHook( self, event ):
        
        if self._HydrusShouldNotProcessInput(): event.Skip()
        else:
            
            ( modifier, key ) = ClientData.GetShortcutFromEvent( event )
            
            if modifier == wx.ACCEL_NORMAL and key in ( wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE ): self._Delete()
            elif modifier == wx.ACCEL_NORMAL and key in ( wx.WXK_SPACE, wx.WXK_NUMPAD_SPACE ): wx.CallAfter( self._PausePlaySlideshow )
            elif modifier == wx.ACCEL_NORMAL and key in ( ord( '+' ), wx.WXK_ADD, wx.WXK_NUMPAD_ADD ): self._ZoomIn()
            elif modifier == wx.ACCEL_NORMAL and key in ( ord( '-' ), wx.WXK_SUBTRACT, wx.WXK_NUMPAD_SUBTRACT ): self._ZoomOut()
            elif modifier == wx.ACCEL_NORMAL and key == ord( 'Z' ): self._ZoomSwitch()
            elif modifier == wx.ACCEL_NORMAL and key in ( wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER, wx.WXK_ESCAPE ): self._Close()
            elif modifier == wx.ACCEL_CTRL and key == ord( 'C' ):
                with wx.BusyCursor(): wx.GetApp().Write( 'copy_files', ( self._current_display_media.GetHash(), ) )
            else:
                
                key_dict = HC.options[ 'shortcuts' ][ modifier ]
                
                if key in key_dict:
                    
                    action = key_dict[ key ]
                    
                    self.ProcessEvent( wx.CommandEvent( commandType = wx.wxEVT_COMMAND_MENU_SELECTED, winid = ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( action ) ) )
                    
                else: event.Skip()
                
            
        
    
    def EventMenu( self, event ):
        
        # is None bit means this is prob from a keydown->menu event
        if event.GetEventObject() is None and self._HydrusShouldNotProcessInput(): event.Skip()
        else:
            
            action = ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetAction( event.GetId() )
            
            if action is not None:
                
                ( command, data ) = action
                
                if command == 'archive': self._Archive()
                elif command == 'copy_files':
                    with wx.BusyCursor(): wx.GetApp().Write( 'copy_files', ( self._current_display_media.GetHash(), ) )
                elif command == 'copy_hash': self._CopyHashToClipboard()
                elif command == 'copy_local_url': self._CopyLocalUrlToClipboard()
                elif command == 'copy_path': self._CopyPathToClipboard()
                elif command == 'delete': self._Delete()
                elif command == 'fullscreen_switch': self._FullscreenSwitch()
                elif command == 'first': self._ShowFirst()
                elif command == 'last': self._ShowLast()
                elif command == 'previous': self._ShowPrevious()
                elif command == 'next': self._ShowNext()
                elif command == 'frame_back': self._media_container.GotoPreviousOrNextFrame( -1 )
                elif command == 'frame_next': self._media_container.GotoPreviousOrNextFrame( 1 )
                elif command == 'inbox': self._Inbox()
                elif command == 'manage_ratings': self._ManageRatings()
                elif command == 'manage_tags': wx.CallAfter( self._ManageTags )
                elif command == 'open_externally': self._OpenExternally()
                elif command in ( 'pan_up', 'pan_down', 'pan_left', 'pan_right' ):
                    
                    distance = 20
                    
                    if command == 'pan_up': self._DoManualPan( 0, -distance )
                    elif command == 'pan_down': self._DoManualPan( 0, distance )
                    elif command == 'pan_left': self._DoManualPan( -distance, 0 )
                    elif command == 'pan_right': self._DoManualPan( distance, 0 )
                    
                elif command == 'remove': self._Remove()
                elif command == 'slideshow': wx.CallAfter( self._StartSlideshow, data )
                elif command == 'slideshow_pause_play': wx.CallAfter( self._PausePlaySlideshow )
                elif command == 'zoom_in': self._ZoomIn()
                elif command == 'zoom_out': self._ZoomOut()
                elif command == 'zoom_switch': self._ZoomSwitch()
                else: event.Skip()
                
            
        
    
    def EventMouseWheel( self, event ):
        
        if self._HydrusShouldNotProcessInput(): event.Skip()
        else:
            
            if event.CmdDown():
                
                if event.GetWheelRotation() > 0: self._ZoomIn()
                else: self._ZoomOut()
                
            else:
                
                if event.GetWheelRotation() > 0: self._ShowPrevious()
                else: self._ShowNext()
                
            
        
    
    def EventShowMenu( self, event ):
        
        services = wx.GetApp().GetManager( 'services' ).GetServices()
        
        local_ratings_services = [ service for service in services if service.GetServiceType() in ( HC.LOCAL_RATING_LIKE, HC.LOCAL_RATING_NUMERICAL ) ]
        
        i_can_post_ratings = len( local_ratings_services ) > 0
        
        self._last_drag_coordinates = None # to stop successive right-click drag warp bug
        
        menu = wx.Menu()
        
        menu.Append( CC.ID_NULL, self._current_display_media.GetPrettyInfo() )
        menu.Append( CC.ID_NULL, self._current_display_media.GetPrettyAge() )
        
        menu.AppendSeparator()
        
        menu.Append( CC.ID_NULL, 'current zoom: ' + HydrusData.ConvertZoomToPercentage( self._current_zoom ) )
        
        menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'zoom_in' ), 'zoom in' )
        menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'zoom_out' ), 'zoom out' )
        
        #
        
        if self._current_display_media.GetMime() not in EMBED_BUTTON_MIMES + NON_ZOOMABLE_MIMES:
            
            ( my_width, my_height ) = self.GetClientSize()
            
            ( media_width, media_height ) = self._current_display_media.GetResolution()
            
            if self._current_zoom == 1.0:
                
                if media_width > my_width or media_height > my_height: menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'zoom_switch' ), 'zoom fit' )
                
            else: menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'zoom_switch' ), 'zoom full' )
            
        
        #
        
        menu.AppendSeparator()
        
        manage_menu = wx.Menu()
        
        manage_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'manage_tags' ), 'tags' )
        
        if i_can_post_ratings: manage_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'manage_ratings' ), 'ratings' )
        
        menu.AppendMenu( CC.ID_NULL, 'manage', manage_menu )
        
        menu.AppendSeparator()
        
        if self._current_display_media.HasInbox(): menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'archive' ), '&archive' )
        if self._current_display_media.HasArchive(): menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'inbox' ), 'return to &inbox' )
        menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'remove', CC.LOCAL_FILE_SERVICE_KEY ), '&remove' )
        menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'delete', CC.LOCAL_FILE_SERVICE_KEY ), '&delete' )
        
        menu.AppendSeparator()
        
        menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'open_externally', CC.LOCAL_FILE_SERVICE_KEY ), '&open externally' )
        
        share_menu = wx.Menu()
        
        copy_menu = wx.Menu()
        
        copy_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'copy_files' ), 'file' )
        copy_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'copy_hash' ), 'hash' )
        copy_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'copy_path' ), 'path' )
        copy_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'copy_local_url' ), 'local url' )
        
        share_menu.AppendMenu( CC.ID_NULL, 'copy', copy_menu )
        
        menu.AppendMenu( CC.ID_NULL, 'share', share_menu )
        
        menu.AppendSeparator()
        
        slideshow = wx.Menu()
        
        slideshow.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'slideshow', 1000 ), '1 second' )
        slideshow.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'slideshow', 5000 ), '5 seconds' )
        slideshow.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'slideshow', 10000 ), '10 seconds' )
        slideshow.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'slideshow', 30000 ), '30 seconds' )
        slideshow.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'slideshow', 60000 ), '60 seconds' )
        slideshow.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'slideshow', 80 ), 'william gibson' )
        slideshow.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'slideshow' ), 'custom interval' )
        
        menu.AppendMenu( CC.ID_NULL, 'start slideshow', slideshow )
        
        if self._timer_slideshow.IsRunning(): menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'slideshow_pause_play' ), 'stop slideshow' )
        
        menu.AppendSeparator()
        
        if self.IsFullScreen(): menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'fullscreen_switch' ), 'exit fullscreen' )
        else: menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'fullscreen_switch' ), 'go fullscreen' )
        
        self._menu_open = True
        
        if self._timer_slideshow.IsRunning():
            
            self._timer_slideshow.Stop()
            
            self.PopupMenu( menu )
            
            self._timer_slideshow.Start()
            
        else:
            
            self.PopupMenu( menu )
            
        
        self._menu_open = False
        
        wx.CallAfter( menu.Destroy )
        
        event.Skip()
        
    
    def TIMEREventSlideshow( self, event ): self._ShowNext()
    
class CanvasFullscreenMediaListCustomFilter( CanvasFullscreenMediaListNavigable ):
    
    def __init__( self, my_parent, page_key, file_service_key, media_results, shortcuts ):
        
        CanvasFullscreenMediaListNavigable.__init__( self, my_parent, page_key, file_service_key, media_results )
        
        self._shortcuts = shortcuts
        
        self.Bind( wx.EVT_LEFT_DCLICK, self.EventClose )
        self.Bind( wx.EVT_MIDDLE_DOWN, self.EventClose )
        self.Bind( wx.EVT_MOUSEWHEEL, self.EventMouseWheel )
        self.Bind( wx.EVT_RIGHT_DOWN, self.EventShowMenu )
        
        self.Bind( wx.EVT_MENU, self.EventMenu )
        
        self.Bind( wx.EVT_CHAR_HOOK, self.EventCharHook )
        
        self.SetMedia( self._GetFirst() )
        
        self._hover_commands.AddCommand( 'edit shortcuts', self.EventShortcuts )
        
        HydrusGlobals.pubsub.sub( self, 'AddMediaResults', 'add_media_results' )
        
    
    def _CopyLocalUrlToClipboard( self ):
        
        local_url = 'http://127.0.0.1:' + str( HC.options[ 'local_port' ] ) + '/file?hash=' + self._current_display_media.GetHash().encode( 'hex' )
        
        HydrusGlobals.pubsub.pub( 'clipboard', 'text', local_url )
        
    
    def _CopyPathToClipboard( self ):
        
        path = ClientFiles.GetFilePath( self._current_display_media.GetHash(), self._current_display_media.GetMime() )
        
        HydrusGlobals.pubsub.pub( 'clipboard', 'text', path )
        
    
    def _Inbox( self ): wx.GetApp().Write( 'content_updates', { CC.LOCAL_FILE_SERVICE_KEY : [ HydrusData.ContentUpdate( HC.CONTENT_DATA_TYPE_FILES, HC.CONTENT_UPDATE_INBOX, ( self._current_display_media.GetHash(), ) ) ] } )
    
    def EventShortcuts( self, event ):
        
        with ClientGUIDialogs.DialogShortcuts( self ) as dlg:
            
            if dlg.ShowModal() == wx.ID_OK: self._shortcuts = dlg.GetShortcuts()
            
        
    
    def EventCharHook( self, event ):
        
        if self._HydrusShouldNotProcessInput(): event.Skip()
        else:
            
            ( modifier, key ) = ClientData.GetShortcutFromEvent( event )
            
            action = self._shortcuts.GetKeyboardAction( modifier, key )
            
            if action is not None:
                
                ( service_key, data ) = action
                
                if service_key is None:
                    
                    if data == 'archive': self._Archive()
                    elif data == 'delete': self._Delete()
                    elif data == 'frame_back': self._media_container.GotoPreviousOrNextFrame( -1 )
                    elif data == 'frame_next': self._media_container.GotoPreviousOrNextFrame( 1 )
                    elif data == 'fullscreen_switch': self._FullscreenSwitch()
                    elif data == 'inbox': self._Inbox()
                    elif data == 'manage_ratings': self._ManageRatings()
                    elif data == 'manage_tags': wx.CallAfter( self._ManageTags )
                    elif data in ( 'pan_up', 'pan_down', 'pan_left', 'pan_right' ):
                        
                        distance = 20
                        
                        if data == 'pan_up': self._DoManualPan( 0, -distance )
                        elif data == 'pan_down': self._DoManualPan( 0, distance )
                        elif data == 'pan_left': self._DoManualPan( -distance, 0 )
                        elif data == 'pan_right': self._DoManualPan( distance, 0 )
                        
                    elif data == 'first': self._ShowFirst()
                    elif data == 'last': self._ShowLast()
                    elif data == 'previous': self._ShowPrevious()
                    elif data == 'next': self._ShowNext()
                    
                else:
                    
                    service = wx.GetApp().GetManager( 'services' ).GetService( service_key )
                    
                    service_type = service.GetServiceType()
                    
                    hashes = ( self._current_display_media.GetHash(), )
                    
                    if service_type in ( HC.LOCAL_TAG, HC.TAG_REPOSITORY ):
                        
                        tag = data
                        
                        tags_manager = self._current_display_media.GetTagsManager()
                        
                        current = tags_manager.GetCurrent()
                        pending = tags_manager.GetPending()
                        petitioned = tags_manager.GetPetitioned()
                        
                        if service_type == HC.LOCAL_TAG:
                            
                            tags = [ tag ]
                            
                            if tag in current: content_update_action = HC.CONTENT_UPDATE_DELETE
                            else:
                                
                                content_update_action = HC.CONTENT_UPDATE_ADD
                                
                                tag_parents_manager = wx.GetApp().GetManager( 'tag_parents' )
                                
                                parents = tag_parents_manager.GetParents( service_key, tag )
                                
                                tags.extend( parents )
                                
                            
                            rows = [ ( tag, hashes ) for tag in tags ]
                            
                        else:
                            
                            if tag in current:
                                
                                if tag in petitioned: edit_log = [ ( HC.CONTENT_UPDATE_RESCIND_PETITION, tag ) ]
                                else:
                                    
                                    message = 'Enter a reason for this tag to be removed. A janitor will review your petition.'
                                    
                                    with ClientGUIDialogs.DialogTextEntry( self, message ) as dlg:
                                        
                                        if dlg.ShowModal() == wx.ID_OK:
                                            
                                            content_update_action = HC.CONTENT_UPDATE_PETITION
                                            
                                            rows = [ ( dlg.GetValue(), tag, hashes ) ]
                                            
                                        else: return
                                        
                                    
                                
                            else:
                                
                                tags = [ tag ]
                                
                                if tag in pending: content_update_action = HC.CONTENT_UPDATE_RESCIND_PENDING
                                else:
                                    
                                    content_update_action = HC.CONTENT_UPDATE_PENDING
                                    
                                    tag_parents_manager = wx.GetApp().GetManager( 'tag_parents' )
                                    
                                    parents = tag_parents_manager.GetParents( service_key, tag )
                                    
                                    tags.extend( parents )
                                    
                                
                                rows = [ ( tag, hashes ) for tag in tags ]
                                
                            
                        
                        content_updates = [ HydrusData.ContentUpdate( HC.CONTENT_DATA_TYPE_MAPPINGS, content_update_action, row ) for row in rows ]
                        
                    elif service_type in ( HC.LOCAL_RATING_LIKE, HC.LOCAL_RATING_NUMERICAL ):
                        
                        # maybe this needs to be more complicated, if action is, say, remove the rating?
                        # ratings needs a good look at anyway
                        
                        rating = data
                        
                        row = ( rating, hashes )
                        
                        content_updates = [ HydrusData.ContentUpdate( HC.CONTENT_DATA_TYPE_RATINGS, HC.CONTENT_UPDATE_ADD, row ) ]
                        
                    
                    wx.GetApp().Write( 'content_updates', { service_key : content_updates } )
                    
                
            else:
                
                if modifier == wx.ACCEL_NORMAL and key in ( ord( '+' ), wx.WXK_ADD, wx.WXK_NUMPAD_ADD ): self._ZoomIn()
                elif modifier == wx.ACCEL_NORMAL and key in ( ord( '-' ), wx.WXK_SUBTRACT, wx.WXK_NUMPAD_SUBTRACT ): self._ZoomOut()
                elif modifier == wx.ACCEL_NORMAL and key == ord( 'Z' ): self._ZoomSwitch()
                elif modifier == wx.ACCEL_NORMAL and key in ( wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER, wx.WXK_ESCAPE ): self._Close()
                elif modifier == wx.ACCEL_CTRL and key == ord( 'C' ):
                    with wx.BusyCursor(): wx.GetApp().Write( 'copy_files', ( self._current_display_media.GetHash(), ) )
                else:
                    
                    key_dict = HC.options[ 'shortcuts' ][ modifier ]
                    
                    if key in key_dict:
                        
                        action = key_dict[ key ]
                        
                        self.ProcessEvent( wx.CommandEvent( commandType = wx.wxEVT_COMMAND_MENU_SELECTED, winid = ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( action ) ) )
                        
                    else: event.Skip()
                    
                
            
        
    
    def EventMenu( self, event ):
        
        # is None bit means this is prob from a keydown->menu event
        if event.GetEventObject() is None and self._HydrusShouldNotProcessInput(): event.Skip()
        else:
            
            action = ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetAction( event.GetId() )
            
            if action is not None:
                
                ( command, data ) = action
                
                if command == 'archive': self._Archive()
                elif command == 'copy_files':
                    with wx.BusyCursor(): wx.GetApp().Write( 'copy_files', ( self._current_display_media.GetHash(), ) )
                elif command == 'copy_hash': self._CopyHashToClipboard()
                elif command == 'copy_local_url': self._CopyLocalUrlToClipboard()
                elif command == 'copy_path': self._CopyPathToClipboard()
                elif command == 'delete': self._Delete()
                elif command == 'fullscreen_switch': self._FullscreenSwitch()
                elif command == 'first': self._ShowFirst()
                elif command == 'last': self._ShowLast()
                elif command == 'previous': self._ShowPrevious()
                elif command == 'next': self._ShowNext()
                elif command == 'frame_back': self._media_container.GotoPreviousOrNextFrame( -1 )
                elif command == 'frame_next': self._media_container.GotoPreviousOrNextFrame( 1 )
                elif command == 'inbox': self._Inbox()
                elif command == 'manage_ratings': self._ManageRatings()
                elif command == 'manage_tags': wx.CallAfter( self._ManageTags )
                elif command == 'open_externally': self._OpenExternally()
                elif command == 'remove': self._Remove()
                elif command == 'zoom_in': self._ZoomIn()
                elif command == 'zoom_out': self._ZoomOut()
                elif command == 'zoom_switch': self._ZoomSwitch()
                else: event.Skip()
                
            
        
    
    def EventMouseWheel( self, event ):
        
        if self._HydrusShouldNotProcessInput(): event.Skip()
        else:
            
            if event.CmdDown():
                
                if event.GetWheelRotation() > 0: self._ZoomIn()
                else: self._ZoomOut()
                
            else:
                
                if event.GetWheelRotation() > 0: self._ShowPrevious()
                else: self._ShowNext()
                
            
        
    
    def EventShowMenu( self, event ):
        
        services = wx.GetApp().GetManager( 'services' ).GetServices()
        
        local_ratings_services = [ service for service in services if service.GetServiceType() in ( HC.LOCAL_RATING_LIKE, HC.LOCAL_RATING_NUMERICAL ) ]
        
        i_can_post_ratings = len( local_ratings_services ) > 0
        
        #
        
        self._last_drag_coordinates = None # to stop successive right-click drag warp bug
        
        menu = wx.Menu()
        
        menu.Append( CC.ID_NULL, self._current_display_media.GetPrettyInfo() )
        menu.Append( CC.ID_NULL, self._current_display_media.GetPrettyAge() )
        
        menu.AppendSeparator()
        
        menu.Append( CC.ID_NULL, 'current zoom: ' + HydrusData.ConvertZoomToPercentage( self._current_zoom ) )
        
        menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'zoom_in' ), 'zoom in' )
        menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'zoom_out' ), 'zoom out' )
        
        #
        
        if self._current_display_media.GetMime() not in EMBED_BUTTON_MIMES + NON_ZOOMABLE_MIMES:
            
            ( my_width, my_height ) = self.GetClientSize()
            
            ( media_width, media_height ) = self._current_display_media.GetResolution()
            
            if self._current_zoom == 1.0:
                
                if media_width > my_width or media_height > my_height: menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'zoom_switch' ), 'zoom fit' )
                
            else: menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'zoom_switch' ), 'zoom full' )
            
        
        #
        
        menu.AppendSeparator()
        
        manage_menu = wx.Menu()
        
        manage_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'manage_tags' ), 'tags' )
        
        if i_can_post_ratings: manage_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'manage_ratings' ), 'ratings' )
        
        menu.AppendMenu( CC.ID_NULL, 'manage', manage_menu )
        
        menu.AppendSeparator()
        
        if self._current_display_media.HasInbox(): menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'archive' ), '&archive' )
        if self._current_display_media.HasArchive(): menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'inbox' ), 'return to &inbox' )
        menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'remove' ), '&remove' )
        menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'delete', CC.LOCAL_FILE_SERVICE_KEY ), '&delete' )
        
        menu.AppendSeparator()
        
        menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'open_externally', CC.LOCAL_FILE_SERVICE_KEY ), '&open externally' )
        
        share_menu = wx.Menu()
        
        copy_menu = wx.Menu()
        
        copy_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'copy_files' ), 'file' )
        copy_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'copy_hash' ), 'hash' )
        copy_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'copy_path' ), 'path' )
        copy_menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'copy_local_url' ), 'local url' )
        
        share_menu.AppendMenu( CC.ID_NULL, 'copy', copy_menu )
        
        menu.AppendMenu( CC.ID_NULL, 'share', share_menu )
        
        menu.AppendSeparator()
        
        if self.IsFullScreen(): menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'fullscreen_switch' ), 'exit fullscreen' )
        else: menu.Append( ClientCaches.MENU_EVENT_ID_TO_ACTION_CACHE.GetId( 'fullscreen_switch' ), 'go fullscreen' )
        
        self._menu_open = True
        
        self.PopupMenu( menu )
        
        self._menu_open = False
        
        wx.CallAfter( menu.Destroy )
        
        event.Skip()
        
    
class RatingsFilterFrameLike( CanvasFullscreenMediaListFilter ):
    
    def __init__( self, my_parent, page_key, service_key, media_results ):
        
        CanvasFullscreenMediaListFilter.__init__( self, my_parent, page_key, CC.LOCAL_FILE_SERVICE_KEY, media_results )
        
        self._rating_service_key = service_key
        self._service = wx.GetApp().GetManager( 'services' ).GetService( service_key )
        
        self._hover_commands.SetNavigable( False )
        
    
    def _Close( self ):
        
        if not self._HydrusShouldNotProcessInput():
            
            if len( self._kept ) > 0 or len( self._deleted ) > 0:
                
                ( like, dislike ) = self._service.GetLikeDislike()
                
                with ClientGUIDialogs.DialogFinishFiltering( self, len( self._kept ), len( self._deleted ), keep = like, delete = dislike ) as dlg:
                    
                    modal = dlg.ShowModal()
                    
                    if modal == wx.ID_CANCEL:
                        
                        if self._current_media in self._kept: self._kept.remove( self._current_media )
                        if self._current_media in self._deleted: self._deleted.remove( self._current_media )
                        
                    else:
                        
                        if modal == wx.ID_YES:
                            
                            self._deleted_hashes = [ media.GetHash() for media in self._deleted ]
                            self._kept_hashes = [ media.GetHash() for media in self._kept ]
                            
                            content_updates = []
                            
                            content_updates.extend( [ HydrusData.ContentUpdate( HC.CONTENT_DATA_TYPE_RATINGS, HC.CONTENT_UPDATE_ADD, ( 0.0, set( ( hash, ) ) ) ) for hash in self._deleted_hashes ] )
                            content_updates.extend( [ HydrusData.ContentUpdate( HC.CONTENT_DATA_TYPE_RATINGS, HC.CONTENT_UPDATE_ADD, ( 1.0, set( ( hash, ) ) ) ) for hash in self._kept_hashes ] )
                            
                            wx.GetApp().Write( 'content_updates', { self._rating_service_key : content_updates } )
                            
                            self._kept = set()
                            self._deleted = set()
                            
                        
                        CanvasFullscreenMediaList._Close( self )
                        
                    
                
            else: CanvasFullscreenMediaList._Close( self )
            
        
    
class MediaContainer( wx.Window ):
    
    def __init__( self, parent, image_cache, media, initial_size, initial_position ):
        
        wx.Window.__init__( self, parent, size = initial_size, pos = initial_position )
        
        self._image_cache = image_cache
        self._media = media
        self._media_window = None
        self._embed_button = None
        
        self._MakeMediaWindow()
        
        self.Bind( wx.EVT_SIZE, self.EventResize )
        self.Bind( wx.EVT_MOUSE_EVENTS, self.EventPropagateMouse )
        
        self.EventResize( None )
        
    
    def _MakeMediaWindow( self, do_embed_button = True ):
        
        ( media_initial_size, media_initial_position ) = ( self.GetClientSize(), ( 0, 0 ) )
        
        if do_embed_button and self._media.GetMime() in EMBED_BUTTON_MIMES:
            
            self._embed_button = EmbedButton( self, media_initial_size )
            self._embed_button.Bind( wx.EVT_LEFT_DOWN, self.EventEmbedButton )
            
            return
            
        elif self._embed_button is not None: self._embed_button.Hide()
        
        if ShouldHaveAnimationBar( self._media ):
            
            ( x, y ) = media_initial_size
            
            media_initial_size = ( x, y - ANIMATED_SCANBAR_HEIGHT )
            
        
        if self._media.GetMime() in HC.IMAGES:
            
            if ShouldHaveAnimationBar( self._media ): self._media_window = Animation( self, self._media, media_initial_size, media_initial_position )
            else: self._media_window = self._media_window = StaticImage( self, self._media, self._image_cache, media_initial_size, media_initial_position )
            
        elif self._media.GetMime() in HC.NATIVE_VIDEO: self._media_window = Animation( self, self._media, media_initial_size, media_initial_position )
        elif self._media.GetMime() == HC.APPLICATION_FLASH:
            
            self._media_window = wx.lib.flashwin.FlashWindow( self, size = media_initial_size, pos = media_initial_position )
            
            self._media_window.movie = ClientFiles.GetFilePath( self._media.GetHash(), HC.APPLICATION_FLASH )
            
        elif self._media.GetMime() == HC.VIDEO_FLV:
            
            self._media_window = wx.lib.flashwin.FlashWindow( self, size = media_initial_size, pos = media_initial_position )
            
            flash_vars = []
            flash_vars.append( ( 'flv', ClientFiles.GetFilePath( self._media.GetHash(), HC.VIDEO_FLV ) ) )
            flash_vars.append( ( 'margin', '0' ) )
            flash_vars.append( ( 'autoload', '1' ) )
            flash_vars.append( ( 'autoplay', '1' ) )
            flash_vars.append( ( 'showvolume', '1' ) )
            flash_vars.append( ( 'showtime', '1' ) )
            flash_vars.append( ( 'loop', '1' ) )
            
            f = urllib.urlencode( flash_vars )
            
            self._media_window.flashvars = f
            self._media_window.movie = HC.STATIC_DIR + os.path.sep + 'player_flv_maxi_1.6.0.swf'
            
        elif self._media.GetMime() == HC.APPLICATION_PDF: self._media_window = PDFButton( self, self._media.GetHash(), media_initial_size )
        elif self._media.GetMime() in HC.AUDIO: self._media_window = EmbedWindowAudio( self, self._media.GetHash(), self._media.GetMime(), media_initial_size )
        
        if ShouldHaveAnimationBar( self._media ):
            
            self._animation_bar = AnimationBar( self, self._media, self._media_window )
            
            if self._media.GetMime() != HC.APPLICATION_FLASH: self._media_window.SetAnimationBar( self._animation_bar )
            
        
    
    def EventEmbedButton( self, event ):
        
        self._MakeMediaWindow( do_embed_button = False )
        
    
    def EventPropagateMouse( self, event ):
        
        if self._media.GetMime() in HC.IMAGES or self._media.GetMime() in HC.VIDEO:
            
            screen_position = self.ClientToScreen( event.GetPosition() )
            ( x, y ) = self.GetParent().ScreenToClient( screen_position )
            
            event.SetX( x )
            event.SetY( y )
            
            event.ResumePropagation( 1 )
            event.Skip()
            
        
    
    def EventResize( self, event ):
        
        ( my_width, my_height ) = self.GetClientSize()
        
        if self._media_window is None:
            
            self._embed_button.SetSize( ( my_width, my_height ) )
            
        else:
            
            ( media_width, media_height ) = ( my_width, my_height )
            
            if ShouldHaveAnimationBar( self._media ):
                
                media_height -= ANIMATED_SCANBAR_HEIGHT
                
                self._animation_bar.SetSize( ( my_width, ANIMATED_SCANBAR_HEIGHT ) )
                self._animation_bar.SetPosition( ( 0, my_height - ANIMATED_SCANBAR_HEIGHT ) )
                
            
            self._media_window.SetSize( ( media_width, media_height ) )
            self._media_window.SetPosition( ( 0, 0 ) )
            
        
    
    def GotoPreviousOrNextFrame( self, direction ):
        
        if self._media_window is not None:
            
            if ShouldHaveAnimationBar( self._media ):
                
                current_frame_index = self._media_window.CurrentFrame()
                
                num_frames = self._media.GetNumFrames()
                
                if direction == 1:
                    
                    if current_frame_index == num_frames - 1: current_frame_index = 0
                    else: current_frame_index += 1
                    
                else:
                    
                    if current_frame_index == 0: current_frame_index = num_frames - 1
                    else: current_frame_index -= 1
                    
                
                self._media_window.GotoFrame( current_frame_index )
                self._animation_bar.GotoFrame( current_frame_index )
                
            
        
    
class EmbedButton( wx.Window ):
    
    def __init__( self, parent, size ):
        
        wx.Window.__init__( self, parent, size = size )
        
        self._dirty = True
        
        self._canvas_bmp = wx.EmptyBitmap( 0, 0, 24 )
        
        self.Bind( wx.EVT_PAINT, self.EventPaint )
        self.Bind( wx.EVT_SIZE, self.EventResize )
        self.Bind( wx.EVT_ERASE_BACKGROUND, self.EventEraseBackground )
        
    
    def _Redraw( self ):
        
        ( x, y ) = self.GetClientSize()
        
        self._canvas_bmp = wx.EmptyBitmap( x, y, 24 )
        
        dc = wx.MemoryDC( self._canvas_bmp )
        
        dc.SetBackground( wx.Brush( wx.Colour( *HC.options[ 'gui_colours' ][ 'media_background' ] ) ) )
        
        dc.Clear() # gcdc doesn't support clear
        
        dc = wx.GCDC( dc )
        
        center_x = x / 2
        center_y = y / 2
        radius = min( center_x, center_y ) - 5
        
        dc.SetPen( wx.TRANSPARENT_PEN )
        
        dc.SetBrush( wx.Brush( wx.Colour( 235, 235, 235 ) ) )
        
        dc.DrawCircle( center_x, center_y, radius )
        
        dc.SetBrush( wx.Brush( wx.Colour( *HC.options[ 'gui_colours' ][ 'media_background' ] ) ) )
        
        m = ( 2 ** 0.5 ) / 2 # 45 degree angle
        
        half_radius = radius / 2
        
        angle_half_radius = m * half_radius
        
        points = []
        
        points.append( ( center_x - angle_half_radius, center_y - angle_half_radius ) )
        points.append( ( center_x + half_radius, center_y ) )
        points.append( ( center_x - angle_half_radius, center_y + angle_half_radius ) )
        
        dc.DrawPolygon( points )
        
        #
        
        dc.SetPen( wx.Pen( wx.Colour( 215, 215, 215 ) ) )
        
        dc.SetBrush( wx.TRANSPARENT_BRUSH )
        
        dc.DrawRectangle( 0, 0, x, y )
        
        self._dirty = False
        
    
    def EventEraseBackground( self, event ): pass
    
    def EventPaint( self, event ):
        
        if self._dirty:
            
            self._Redraw()
            
        
        wx.BufferedPaintDC( self, self._canvas_bmp )
        
    
    def EventResize( self, event ):
        
        ( my_width, my_height ) = self.GetClientSize()
        
        ( current_bmp_width, current_bmp_height ) = self._canvas_bmp.GetSize()
        
        if my_width != current_bmp_width or my_height != current_bmp_height:
            
            if my_width > 0 and my_height > 0:
                
                self._dirty = True
                
                self.Refresh()
                
            
        
    
class EmbedWindowAudio( wx.Window ):
    
    def __init__( self, parent, hash, mime, size ):
        
        wx.Window.__init__( self, parent, size = size )
        
        self.SetCursor( wx.StockCursor( wx.CURSOR_ARROW ) )
        
        self._hash = hash
        self._mime = mime
        
        vbox = wx.BoxSizer( wx.VERTICAL )
        
        ( width, height ) = size
        
        media_height = height - 45
        
        self._media_ctrl = wx.media.MediaCtrl( self, size = ( width, media_height ) )
        self._media_ctrl.Hide()
        
        self._embed_button = EmbedButton( self, size = ( width, media_height ) )
        self._embed_button.Bind( wx.EVT_LEFT_DOWN, self.EventEmbedButton )
        
        launch_button = wx.Button( self, label = 'launch ' + HC.mime_string_lookup[ mime ] + ' externally', size = ( width, 45 ), pos = ( 0, media_height ) )
        launch_button.Bind( wx.EVT_BUTTON, self.EventLaunchButton )
        
    
    def EventEmbedButton( self, event ):
        
        self._embed_button.Hide()
        
        self._media_ctrl.ShowPlayerControls( wx.media.MEDIACTRLPLAYERCONTROLS_DEFAULT )
        
        path = ClientFiles.GetFilePath( self._hash, self._mime )
        
        self._media_ctrl.Load( path )
        
        self._media_ctrl.Show()
        
    
    def EventLaunchButton( self, event ):
        
        path = ClientFiles.GetFilePath( self._hash, self._mime )
        
        HydrusFileHandling.LaunchFile( path )
        
    
class PDFButton( wx.Button ):
    
    def __init__( self, parent, hash, size ):
        
        wx.Button.__init__( self, parent, label = 'launch pdf', size = size )
        
        self.SetCursor( wx.StockCursor( wx.CURSOR_ARROW ) )
        
        self._hash = hash
        
        self.Bind( wx.EVT_BUTTON, self.EventButton )
        
    
    def EventButton( self, event ):
        
        path = ClientFiles.GetFilePath( self._hash, HC.APPLICATION_PDF )
        
        HydrusFileHandling.LaunchFile( path )
        
    
class StaticImage( wx.Window ):
    
    def __init__( self, parent, media, image_cache, initial_size, initial_position ):
        
        wx.Window.__init__( self, parent, size = initial_size, pos = initial_position )
        
        self._dirty = True
        
        self._media = media
        self._image_container = None
        self._image_cache = image_cache
        
        self._canvas_bmp = wx.EmptyBitmap( 0, 0, 24 )
        
        self._timer_render_wait = wx.Timer( self, id = ID_TIMER_RENDER_WAIT )
        
        self._paused = False
        
        self.Bind( wx.EVT_PAINT, self.EventPaint )
        self.Bind( wx.EVT_SIZE, self.EventResize )
        self.Bind( wx.EVT_TIMER, self.TIMEREventRenderWait, id = ID_TIMER_RENDER_WAIT )
        self.Bind( wx.EVT_MOUSE_EVENTS, self.EventPropagateMouse )
        self.Bind( wx.EVT_ERASE_BACKGROUND, self.EventEraseBackground )
        
        self.EventResize( None )
        
        self._timer_render_wait.Start( 16, wx.TIMER_CONTINUOUS )
        
    
    def _Redraw( self ):
        
        dc = wx.MemoryDC( self._canvas_bmp )
    
        dc.SetBackground( wx.Brush( wx.Colour( *HC.options[ 'gui_colours' ][ 'media_background' ] ) ) )
        
        dc.Clear()
        
        if self._image_container.IsRendered():
            
            hydrus_bitmap = self._image_container.GetHydrusBitmap()
            
            ( my_width, my_height ) = self._canvas_bmp.GetSize()
            
            ( frame_width, frame_height ) = hydrus_bitmap.GetSize()
            
            if frame_height != my_height:
                
                image = hydrus_bitmap.GetWxImage()
                
                image = image.Scale( my_width, my_height, wx.IMAGE_QUALITY_HIGH )
                
                wx_bitmap = wx.BitmapFromImage( image )
                
                wx.CallAfter( image.Destroy )
                
            else: wx_bitmap = hydrus_bitmap.GetWxBitmap()
            
            dc.DrawBitmap( wx_bitmap, 0, 0 )
            
            wx.CallAfter( wx_bitmap.Destroy )
            
        
        self._dirty = False
        
    
    def _SetDirty( self ):
        
        self._dirty = True
        
        self.Refresh()
        
    
    def EventEraseBackground( self, event ): pass
    
    def EventPaint( self, event ):
        
        if self._dirty:
            
            self._Redraw()
            
        
        wx.BufferedPaintDC( self, self._canvas_bmp )
        
    
    def EventPropagateMouse( self, event ):
        
        screen_position = self.ClientToScreen( event.GetPosition() )
        ( x, y ) = self.GetParent().ScreenToClient( screen_position )
        
        event.SetX( x )
        event.SetY( y )
        
        event.ResumePropagation( 1 )
        event.Skip()
        
    
    def EventResize( self, event ):
        
        ( my_width, my_height ) = self.GetClientSize()
        
        ( current_bmp_width, current_bmp_height ) = self._canvas_bmp.GetSize()
        
        if my_width != current_bmp_width or my_height != current_bmp_height:
            
            if my_width > 0 and my_height > 0:
                
                if self._image_container is None: self._image_container = self._image_cache.GetImage( self._media, ( my_width, my_height ) )
                else:
                    
                    ( image_width, image_height ) = self._image_container.GetSize()
                    
                    we_just_zoomed_in = my_width > image_width or my_height > image_height
                    
                    if we_just_zoomed_in and self._image_container.IsScaled():
                        
                        self._image_container = self._image_cache.GetImage( self._media )
                        
                    
                
                wx.CallAfter( self._canvas_bmp.Destroy )
                
                self._canvas_bmp = wx.EmptyBitmap( my_width, my_height, 24 )
                
                self._SetDirty()
                
                if not self._image_container.IsRendered(): self._timer_render_wait.Start( 16, wx.TIMER_CONTINUOUS )
                
            
        
    
    def TIMEREventRenderWait( self, event ):
        
        if self._image_container.IsRendered():
            
            self._SetDirty()
            
            self._timer_render_wait.Stop()
            
        
    